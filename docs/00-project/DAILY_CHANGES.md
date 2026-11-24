# Daily changes

**Status: 📁 DERIVED — an operations log. It decides nothing and asserts no build state.**

One entry per working day, newest first: what reached production, what changed on the server
outside version control, what was decided, and what was deliberately left undone. It exists so a
morning question — *"what happened yesterday, and is any of it waiting on me?"* — is answered in
one place rather than reconstructed from git.

**What this file is not.** It is not the decision record — that is
[`all_lock.md`](../../all_lock.md), indexed by [LOCKED_DECISIONS.md](LOCKED_DECISIONS.md). It is
not the build state — that is [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md), the only
document permitted to assert it. It is not the repository changelog — that is
[CHANGELOG.md](../../CHANGELOG.md), which records what changed in the repository at milestone
granularity. Where any of those disagree with this file, **they win and this file is stale**.

The distinction that earns this file its place: the others record what changed in the *repository*.
This one records what changed in the *running system* — a deploy, a production data operation, a
credential, a permission — including the things that leave no commit behind.

---

## How an entry is kept (from 2026-11-19)

The practice coding-agent teams use for long work across sessions (Anthropic, *Effective harnesses
for long-running agents*): a progress file a fresh session reads first, a task list with a done
flag, and a commit per finished unit. Here: **this file is the progress file**,
[ENTERPRISE_TRACKER.md](ENTERPRISE_TRACKER.md) is the task list, and every batch is a PR. Each
working day gets one entry, newest first, with these headings (omit an empty one):

- **Done** — finished units: PR, commit, verifier verdict.
- **Reached production** — deploys (commit) and what was checked live.
- **Changed on the server (no commit)** — env, data, permissions.
- **In progress** — branch / worktree and the exact next step, so another session can pick it up.
- **Next** — the following unit in the agreed order.
- **Blocked** — on whom, and what is needed (owner, Legal, external).

---

## 2026-11-25

### Done
- W1 "fast first screen" built on `perf/w1-first-screen`, independently verified 10/10 after 4 rounds, UI critic's must-fixes done; PR opened (not deployed). Decisions by the lead: the idle Ask warm-up stays (Ask tap ≈ main, at the cost of one ~150 ms task after the largest paint); one PDF evidence link at 390 lands ~55 px differently from main (row taller than the screen).

### Next
- Owner: "deploy" for W1, then re-measure the live phone scores; test once on a real iPhone (no WebKit on the host).
- W2, M2, M3, S1, B1 per `audit/perf-20261124/PERF-AUDIT.md`, `SERVER-AUDIT.md`, `../mobile-20261124/MOBILE-AUDIT.md`.

---

## 2026-11-24

### Done
- **Full-stack audit U2 "workspace layout"** (AB-225, `AM-471`–`AM-474`) built on `fix/ui-u2` (worktree
  `/root/legalmind-worktrees/ui-u2`, from `2c40bfcf`): one meta row, the brief as one row plus a side panel, one
  strip over the panes, a phone header that folds away, no layout shift, a 343 px phone text column at 390 (273 at 320; audit 237), a sticky
  answer tray for Legal, Report as the third tab, the ⋯ menu renamed with Take back in it; the lawyer is told when a
  contract is sent to or taken back from them, and every note for Legal is kept for the owner. Owner answers Q1–Q5
  (2026-11-24). Not committed; `U2-DESIGN.md` and `U2-BUILD-REPORT.md` in the audit folder. Copy Legal still
  confirms: "No standard settles this, so Legal reviews it."
  Rounds 2–4 (verifier, UI critic, security/legal review): docked brief panel and a phone modal sheet, the
  ⋯ menu in groups, the answer tray's phone behaviour, one short reply line, Legal's note first; server: a
  take-back is in-app only, a send e-mails at most once per 15 minutes, `measured` splits NOT_MEASURED /
  UNCLEAR (display only, proven byte-identical elsewhere over 12 pairs / 83 rows), a re-send resets
  `created_at`, row locks on send/take-back, `notes` visibility pinned by a test. Copy Legal still confirms:
  the two `measured` sentences. Round 5: Esc keeps a typed draft (the field's text is remembered on focus),
  the docked brief sits above the phone bar at 641–899 px, the phone sheet says aria-modal. Owner decisions
  (2026-11-24): c113 sales at 320 accepted at y = 361 (status never clamped); the lawyer's CLS 0.134 at 1024
  accepted as pre-existing (0.268 on base 2c40bfcf).
- **AB-223 batch 8 sub-batch B** (`AM-464`–`AM-467`) built on `feat/case-lessons-b` (worktree
  `/root/legalmind-worktrees/case-lessons-b`, from `96792533`): "already agreed before" on change rows, points and
  the brief; "Signed earlier, for reference" on the client page (owner Q1); triage reasons for a rewritten sentence
  (cap carve-out grown, duty widened, a deadline shortened — shown, never routing); "Checked against our standards
  as …" from each standard's source recorded at import (C-34 still open). Production-copy probe: 0 differences in
  12 pairs / 83 rows, 12 answered keys kept. Not committed; report in the batch folder's BUILD-REPORT-B.md.
  Independent verifier: 9/9 items passed; round 2 fixed D1 (no configuration change), D2, D4, D5 and refused
  declaring signed a version already sent to the client (`AM-465` r3).

### Reached production
- **2c40bfcf** deployed 10:46 IST with `sudo legalmind-deploy` (exit 0): P1 (#336), P3 (#337, migration
  `d340ac8e60fd` ran; its own guard fails unless all six indexes are valid), AB-222 batch 8A (#338), U1 (#339),
  P2 (#340), AB-223 batch 8B (#341). No import or publish step.
- Live check as the sales and lawyer test users through the public URL: login 200; contracts list 3.3 s cold after
  restart, 0.34 s warm; briefs 0.1–0.3 s and carry `status` (incl. FINAL_READY), `not_marked`, `already_agreed`,
  `measured_against`; reviews list carries `version_number` / `version_role`.
- **7ce8a014** (U2, AB-225, PR #343) deployed 15:47 IST, exit 0, no migration. Live as the sales test user: the
  owner's `notes` history on review assignments, `/contracts/{id}/report` answers 200, briefs 0.1–0.3 s.
- **fa76a395** (E1 edge, PR #345) deployed 18:48 IST; the new Edge probes passed. Live: HTTP/2, gzip + Vary on API JSON, upstream keep-alive; sign-in works.

### Changed on the server (no commit)
- CPU weights (owner-approved, critic-corrected): `system.slice` 400; api, `postgresql@16-main`, nginx 400; frontend 300; worker 150 (`systemctl set-property`, live, no restart; undo in ops/README).
- Disk 96% → 87% full (2.3 → 6.3 GB free), owner-approved: 28 worktrees whose branch is merged into main and
  that had no changes removed (branches kept); the deploy tree's 2026-09-11 `frontend/.next-e2e` build output
  removed (git-ignored, rebuilt by the next local e2e run); npm cache cleared. Worktrees with uncommitted work
  and other users' folders left alone.

### Next
- Audit batches U2 (workspace layout: UI-03, UI-04, UI-06, UI-07, Take back into the ⋯ menu), U3 (tables,
  home vs to-do), BE-8; follow-ups (`evidenceLocation` "§N", report body copy pass, "-analysis.docx" name).
- Owner calls: take-back notifies the lawyer and keeps the note; sentence-level "already agreed"; D2
  INTERNAL_REVIEW wording; DB-8 audit count (locked 49.4).

### Blocked
- **Legal (C-34):** which standards measure paper that is not an MSA. Until then the brief only says which set measured it.

## 2026-11-23

### Reached production
- **`febed05f`** (#334, AB-221 batch 5 "our contract came back marked up"). No migration; API and site 200; the new start page
  and the `scope=negotiable` deal list answer as the test sales user; no errors in the API log.
- **`f695622d`** (#330, AB-219 batch 6 "client misreads"). API and site 200, reader legalmind-ingest-v12,
  no errors in the API log; the test contract opens unchanged for the lawyer (its versions are both v11,
  so its rows are untouched by design).
- **`02197bc4`** (#332, AB-220 batch 7 "client details before drafting"). Migration `c5e8a2f4d7b1` ran in the
  deploy; API and site 200; the live client record returns `details_missing` (test sales login). MSA.LEAPSWITCH v3
  created as a DRAFT from published v2 with our CIN locked (ops account); v2 stays live until Legal publishes v3.

### Decided (owner)
- Build the "client details before drafting" batch: Legal's 10-item checklist on the MSA form, stored on
  the client, generation blocked until complete; free checks + a person's verification tick; our CIN locked.

### Done
- **Full-stack audit U1 "UI wrong or risky"** on `fix/ui-u1` (BUILT, browser-checked, not committed, not deployed):
  UI-01 Final/Signed brief status (server), UI-02 Take back confirm, UI-05 client counts, UI-10 two-line names,
  UI-09 Reviews queue words and filter, UI-12 report words, headings and export line. `U1-BUILD-REPORT.md`.
  Round 2 after the UI critic and code verifier: true Take back copy, owner's one-line desktop rule kept with
  facts lines (review list API gains version and client), brief "prepare the final contract" when every change is
  accepted, heading focus after take-back, file name in the audit appendix, one name "Final contract ready".
- **AB-220 batch 7 "client details before drafting"** (`AM-449`–`AM-452`) on `feat/client-details`: spec →
  design plan → independent design review (12 changes) → owner OK → build → UX benchmark of Ironclad / Juro /
  SpotDraft public material (6 additions) → independent verifier, 2 rounds (round 1: unbounded certificate OCR,
  country free text opening the gate, convert using another client's draft, scope loss, a name change not clearing
  the check; round 2: the certificate reader's regex — all fixed).
- **Full-stack audit P1 "speed quick wins"** on `perf/quick-wins` (BUILT, independently verified incl. D1–D3 fixes, not deployed): BE-1, BE-11, DB-3, BE-4, BE-7, request DB timeouts. Measured on a scratch
  copy of the production copy: same-session `/auth/session` beside `/contracts` 1,245 → 39 ms; `/contracts` −15 %,
  `/todo` −14 %; permission queries on the legal list 21 → 1; Ask chat reopen 45 → 0.2 ms SQL.
  Report: `audit/fullstack-audit-20261123/P1-BUILD-REPORT.md`.
- **Full-stack audit P2 "stop recalculating"** on `perf/comparison-cache` (BUILT, not committed, not deployed): BE-2/DB-1 comparison cache (content-hash key, answers/decisions live), BE-3 align once, BE-5 brief once + angles one number + brief fetched once, BE-6 answers/decisions per list, DB-7 review screens, BE-9 template check verdict kept. Scratch production copy: `/contracts` 1.6 → 0.35 s, legal list 1.85 → 0.65 s, `/todo` 1.4 → 0.28 s, brief 1.95 → 0.19 s, template check 7.7 s → 34 ms; 15/15 bodies byte-identical to main; probe 0 differences cold and hot. Report: `audit/fullstack-audit-20261123/P2-BUILD-REPORT.md`.
- **Full-stack audit P3 "database hygiene"** on `perf/db-hygiene` (BUILT, not committed, not deployed): migration `d340ac8e60fd` (six indexes built CONCURRENTLY: DB-2, DB-5), DB-10 lookup, BE-13 Docling logs, P1 leftovers (template check commit removed, upload docstring). Measured on a scratch production copy: largest contract delete 463–487 → 69–76 ms; audit reads at 50× 3–42 ms → ≤0.08 ms. DB-8 proposed only (locked 49.4). Report: `audit/fullstack-audit-20261123/P3-BUILD-REPORT.md`.
- **AB-221 batch 5 "our contract came back marked up"** (`AM-455`–`AM-460`) built on `feat/returned-markup`
  (worktree `/root/legalmind-worktrees/returned-markup`): diagnosis → spec → design → independent design review
  (M1–M8, S1–S11, N1–N8) → owner decisions → build. Not committed; report in the batch folder's BUILD-REPORT.md.
  Round 2 after the independent verifier (D1 bulk-answer 409 on the tracked-only and template bases, D2–D5) and a
  separate UI critic (must-fixes 1–5, should-fixes): fixed, re-walked at 1440/390/320; still not committed.

- **AB-222 batch 8 sub-batch A** (`AM-461`–`AM-463`) built on `feat/case-lessons-a` (worktree
  `/root/legalmind-worktrees/case-lessons-a`): not marked first (highlights read, reader v13), reading fixes
  (table comment, broken figure, row-level origin, restyled heading, punctuation only), commercial observations;
  C-34 registered. Production-copy probe 0 of 12 answered keys moved. Not committed; report in the batch folder's
  BUILD-REPORT-A.md.

### Next
- **U1:** re-verify round 2 → PR → CI (job 15 baselines will move: adopt CI's) → merge; deploy on the owner's OK.
- **Owner (U1):** should taking a contract back from Legal notify the lawyer and keep the Sales note?
- P1: independent verification → PR → CI → merge; deploy only on the owner's OK. Then P2 once batch 5 merges.
- P2: independent verification → PR → CI → merge; deploy only on the owner's OK (first read after a deploy is cold: one list page builds the cache).
- P3: independent verification → PR → CI → merge; deploy only on the owner's OK, then run the ops/README index check. DB-8 needs an owner decision on 49.4.
- **AB-222:** independent verification of `feat/case-lessons-a`, then git; then sub-batch B (items 1, 4, 5).
- **Legal:** on MSA.LEAPSWITCH v3 (draft), re-keep the "Partner" wording point, approve, publish.
- **AB-221:** independent verification of `feat/returned-markup`, then the owner's go to commit, PR and deploy.
- **Legal (Q2, AB-221 `AM-459`):** may the text before the client's tracked edits go back as ours ("Keep our
  wording" on the tracked-only base)? Until then it is withheld.

### Blocked
- **Legal:** LeapSwitch's standard NDA template; our registered office and incorporating Act (Constitution
  §4.1 differs from the MSA template).

---

## 2026-11-20

### Reached production
- **`0acf53b6`** (#328, AB-218 deal brief). Migration `f1a7c3e9d5b2` verified (table
  `deal_positions` + append-only trigger); API 200. Live on the test contract: sales see "With Legal:
  55 changes are being answered. Nothing for you yet." and the client's asks above the tabs; the
  lawyer sees "55 changes to answer, 11 points to decide."
- **`ac0332ea`** (#326, AB-217 batch 2 "cited passage"). Health 200. Live re-check of the test
  contract needs a fresh analysis (stored Reviews read as before by design); done with the next
  release's live check.

### Decided (owner)
- Follow the Ironclad / Juro / SpotDraft / LegalOn pattern, kept simple: batches 3 and 4 merge into
  one "deal brief" release (brief at the top, one label + one action per change, Legal-recorded
  "what we told the client"); themes and interplay stay parked.
- A point whose mapping cites no single clause shows under "Whole contract".

### Done
- **AB-218 batches 3+4 "deal brief"** (`AM-439`–`AM-443`) on `feat/deal-brief`: builder 4 rounds,
  independent verifier (FIX-THEN-SHIP → fixed: wrong "send our reply" status, a missed notice,
  "§N" for whole-contract points in the export, positions writable before Legal, a system-written
  reason); real browser on the real pair as sales and lawyer; production-copy probe 0 keys lost.
- **Client MSA + NDA lawyer report** checked through LegalMind's own pipeline (main, no paid model):
  30 of 37 claims confirmed, 5 corrected, 2 outside LegalMind; LegalMind's own misreads listed in
  `legalmind-clm-local/audit/client-report-verify-20261120/VERIFY.md`.

### Sent (owner-approved)
- The client MSA + NDA review posted to the deal's Slack group DM (main message + 3 comparison tables).

### Done (later)
- **AB-219 batch 6 "client misreads"** (`AM-444`–`AM-448`) on `fix/client-misreads`: diagnosis →
  spec → builder 2 rounds → independent verifier (round 1 FIX-THEN-SHIP: phantom rows on mixed reader
  versions, two triage rules that could leave Legal; fixed). Production-copy route probe: 0 changes.

### In progress
- **AB-219** — PR → CI → merge gate → merge; then the owner's deploy OK.
- **PR #322** (Constitution L1.18; other session) — waiting for the owner's merge OK.

### Next
- Batch 5 "our contract came back marked up"; then the live-test leftovers (whitespace-only change,
  carry answers after "Ask the client", "Annexure A" wording, 20–30 s waits).

### Blocked
- **Owner:** NDA link; keep/archive the audit test contract; close #285, decide #270.
- **Legal:** confirm the case baseline; this deal's positions; never-concede list; annexure
  structure (`AM-414` r6); CIN, 15.5 cross-reference, 17.7.

---

## 2026-11-19

### Done
- **AB-216 batch 1 "redline truth"** (`AM-431`–`AM-434`), PR #324 merged `ab8250b1`. Trigger: a
  client returned our MSA with tracked changes (case notes outside the repo,
  `legalmind-clm-local/audit/client-msa-case-20261119/`). Independent verifier: 3 rounds, 27
  adversarial silent-edit cases, final SHIP after a one-line fix. CI 23/23.
- **Answered-keys probe on a private copy of production** (owner OK): 4 pairs, 12 answered keys,
  0 lost.
- **#323** (`44290f60`): a new contract is always analysed (ids read before the after-commit
  publish); deploy notices a refused nginx reload.
- **#321** (`f6ba1912`): AB-214 + `AM-414` r7 (owner's direct confirmation).
- **AB-217 batch 2 "cited passage"** (`AM-435`–`AM-438`): independent verifier 3 rounds
  (round 1: an R-3 change could hide "two weeks'" notice; round 2: "one hundred (100) days";
  round 3 SHIP with a rule-15 guard). Production-copy probe: 0 of 12 answered keys lost.
- Case-by-case plan approved after a strict three-reviewer team review: 5 batches (redline truth →
  cited passage → what we told the client → one-minute brief → "our contract came back marked up").

### Reached production
- **`44290f60`** (#323) and **`ab8250b1`** (#324). Live check on the test contract as sales and as
  the lawyer: no false "changed without marking it", "Compared with version 1 (what we sent)", the
  client's 3 comments on their rows, no "Sign after", one primary button for the lawyer.
- **nginx restarted 13:16** after a reload was silently refused (`limit_req` key change); the rate
  limit from 14 Nov is now live.

### In progress
- **PR #322** (Constitution L1.18, AB-215; other session) — waiting for the owner's merge OK.

### Next
- Batch 3 "what we told the client" (Legal-only deal positions), batch 4 one-minute brief,
  batch 5 returned-markup start option.

### Blocked
- **Legal:** confirm the case baseline; this deal's positions; the never-concede list; whether
  TERM-NOTICE-NDA-001 should never apply to an MSA (only if the code fix is not enough).

---

## 2026-11-04 → 2026-11-18 (back-filled from git on 2026-11-19; deploy details in CHANGELOG)

- **11-18:** #316 (C-32, 17.7 "six (6)", `AM-401`), #317 (CI picomatch allowlist to 2026-12-18),
  #318/#319 (AB-213: template keeps Sayan's MSA verbatim), #320 (pre-launch QA records).
- **11-17:** #305 (MSA standards aligned to Sayan's MSA), #310 (Next.js advisory), #311 (MSA
  own-wording check), #312 (liability carve-out subject), #313 (template publish), #314/#315
  (production E2E fixes A–D).
- **11-16:** #297/#299/#302 (final package S3–S6), #298 follow-ups, #300/#301/#303 records,
  #304 (lawyer agent S0–S4), #306 (real-question regression), #307/#309 (Priyen's rule, reopen),
  #308 (legal verdicts in the sales view).
- **11-12:** #294 (CLM UX integration), #295 records, #296 (menu scroll flake).
- **11-11:** #292 (decision form no preselect), #293 (Constitution standards `AM-322`).
- **11-09:** #284 (statute marks, L1.16), #288 (agent instructions), #289 (structural check),
  #290 (CI repair), #291 (Ask lawyer batch 1).

---

## 2026-11-03

### Reached production
- **`d2a5243`** — PRs #280 (contract gate + chat file only when asked, AB-143), #281 (contract reading, AB-145), #282 (Ask quality, AB-144), #283 (CloudPe Gemma, AB-146 + the C26 gold fix #282 left failing). Health 200, no failed unit.
- **Server:** DeepSeek (IndieRouter, Together) and Bonsai keys commented out in `/root/.legalmind.env` (402/500; values kept; backup `legalmind.env.before-cloudpe-gemma-2026-11-03`); CloudPe key and base URL added; API + worker restarted.
- **Statutes:** all 17 Acts staged with chunker section-7; the first swap regressed one benchmark case and was rolled back the same minute (live = previous generation; STAGED kept).
- **Backup:** an extra full backup at 17:15 (dump + documents, off-server copy verified) ahead of the disk resize.

---

## 2026-11-02

### Changed on the server (no commit)
- **Gemini credit restored** (owner top-up). Probed: a tiny call and a 15k-token call both 200. IndieRouter DeepSeek still 402 on real-sized calls; Together 402.
- **Ask default model and review model → `gemini`** (were `deepseek`, failing since 2026-10-30). Backup `/root/.legalmind/preserved/legalmind.env.before-gemini-default-2026-11-02`; API restarted; both workers carry it.
- **Redis password set (QA-029).** `requirepass` in `/etc/redis/redis.conf` and in `LEGALMIND_BROKER_URL` (`/root/.legalmind.env`); applied live with `CONFIG SET` (data kept), worker and API restarted. Verified: no-password connections refused (NOAUTH); worker ping pong; rate-limit keys written. Backups `/root/.legalmind/preserved/{redis.conf,legalmind.env}.before-redis-password-2026-11-02`. The rate-limit check made two failed logins for `nobody@example.invalid` (in the audit log).

- **Client-change triage ON** (`LEGALMIND_CHANGE_TRIAGE=on`, `AM-224`): Gemini caught 76 of 82 against-us changes on the client's real MSA (DeepSeek 77). Worker and API restarted. Backup `/root/.legalmind/preserved/legalmind.env.before-change-triage-2026-11-02`; rollback = remove the line + restart.
- **Paid tests (~$1.65 Gemini):** lawyer review on 4 real files; C26 36/50 (was 44 — uncited answers, Q-5); stability 12/12 answered.

### Found
- The daily policy refresh failed since 2026-10-31 (`leapswitch.com` → `www.leapswitch.com` redirect). Ask kept answering from the 2026-10-09 copies. Fix built (AB-141), not deployed.
- The live Leapswitch SLA now says 99.9% for every category (was 99.95% for dual power / private network) — adopted as Constitution L1.15 on the owner's ruling.

### Reached production
- **`ad93cd2` (PR #279)**: shared Ask cache, website policies from www.leapswitch.com, Constitution L1.15, `AM-244`. After deploy: L1.15 ingested (L1.14 superseded); refresh run — the four Leapswitch policies CHANGED (SLA 99.9%), CloudPe unchanged; `LEGALMIND_ASK_CACHE_BACKEND=redis` set (backup `legalmind.env.before-ask-cache-redis-2026-11-02`), API restarted, cross-process smoke test on live Redis passed. C26 on live code 41/50 (was 36/50; uncited answers 7 → 2).
- Deploy refused on `nano.156814.save` (1-byte empty autosave) — moved to `/root/.legalmind/preserved/nano.156814.save.from-deploy-tree-2026-11-02` on the owner's choice.

### Waiting
- G-1 step 2 (wire the contract gate) on `feat/contract-gate-20261102`.

---

## 2026-10-14

### Reached production

- **PRs #191–#195 (`f97fb27`), one deploy: the 2026-10-13 tester-pass fixes and the owner's
  three decisions.** 40 of 43 items fixed (see `BUG_REPORT_2026-10-13.md` § Status):
  - Ask K2–K10;
  - security S1–S6, and S5 as `AM-139`;
  - analysis A1–A8, and A8 as `AM-140` (five corpus expectations, `specification-change`
    label);
  - frontend U1–U10 and ops O1–O8;
  - the lawyer-style answers and K1 as `AM-141`.

  Migration `e5a8c3f1d9b4` (a partial unique index, one CURRENT knowledge source per type) was
  **applied and verified**: `alembic_version` = `e5a8c3f1d9b4`, the index present; production
  had no duplicate CURRENT rows beforehand. No new package.
- **The deploy wrapper was updated** (O1). `ops/production/legalmind-deploy` was installed
  to `/usr/local/sbin/legalmind-deploy`, with the previous copy kept at
  `/root/.legalmind/preserved/legalmind-deploy.before-2026-10-14`. It takes the deploy lock
  before touching the tree and hands it to `ops/deploy.sh`. A second deploy of the same
  commit through it succeeded, which proves it does not refuse its own lock.
- **Checked:**
  - services active and `/health` 200;
  - the migration and the index present;
  - the new prompt (`ask-agent-26`) and edit controls in the live build;
  - no page errors in a real browser.
- **Measured before release** on the knowledge-loaded local copy (production reads are
  blocked for the agent): Priyen's three questions correct in the new style, a client
  dispute answered as a lawyer would, and no compliance verdict on a pasted clause.

## 2026-10-13

### Reached production

- **PRs #175, #176 and #177 (`f664985`), one deploy.**
  - #175 (`AM-135`): in a chat about a contract, a compliance question is answered by the
    evaluator's Findings on the agent path too, and `GET /conversations` takes `has_document`.
  - #176: the document page's Ask runs on the same assistant-ui chat as the Ask page, with that
    document's own chat list. The Ask page lists only chats with no document.
  - #177 (another session): dead code and stale root documents removed.
  - No migration and no new package (`pyproject.toml` changed a comment only).
  - CI: Browser workflows lost its API twice mid-run at `client-profiles.spec.ts:166` (the
    known flake). The same order passed locally, 50/50, and the rerun was green on the merged
    commit. Job 14 (npm audit) fails on `main` too.
  - Checked: services active, `/health` 200, `/conversations?has_document=false` routed (401
    unauthenticated), the new dock and filter in the live chunks, no page errors in a real
    browser.
- **PR #181 (`69edfc1`), with #178 (another session's CI and test-speed change).** Fixes from
  a signed-in tester pass on both Ask surfaces (a local copy of the live build with production's
  Ask settings; the ops credential is not readable by the agent):
  - one border on the document panel's question box;
  - "in three bullet points" answered as bullets on the agent path;
  - a question sent while the panel opens its last chat now waits instead of being dropped;
  - a pasted question over 600 characters collapses to six lines with Show more.
  - No migration and no new package. Browser workflows' first run failed building the
    frontend (Google Fonts download on the runner); the rerun was green.
  - Checked: services active, `/health` 200, the new CSS rule and the collapse in the live
    build, no page errors in a real browser.
- **PRs #185 and #186 (`9b92a77`), one deploy.** #185 ports the owner's 2026-10-08 decision
  A-100: `POST /conversations/{id}/document` withdrawn, a chat with no document reads no
  Dashboard contract, the agent reads the version the reader has open and the answer cache
  keys on it. #186: the owner's 2026-09-29 "no commit without the owner" rule written into
  CLAUDE.md and AGENTS.md, and the 30 Sep session notes. No migration, no new package.
  Checked: services active, `/health` 200, the withdrawn route 404 before authentication.
- **Leftover worktrees resolved (owner: "resolve other", except Diff-Talk).** `report-speed`
  and `rag-framework-ab` parked on `origin/wip/report-speed-20260929` and
  `origin/wip/rag-framework-ab-20261001`; the original A-100 commit kept on
  `origin/wip/ask-review-isolation-20261008`; 19 finished worktrees removed; three stale demo
  servers (ports 3199, 3299, 8299) stopped.
- **PR #188 (`e834617`, `AM-138`/AB-83).** A paste is read for what it asks: no fixed "what
  would you like to know?" reply; a paste over 5,000 characters is a "Pasted text" card;
  titles are the first real question or sentence; the edit pencil on pasted messages; the
  reader's message folds with Show more and carries Copy and Edit beneath. Main took
  `AM-136`/`AM-137` for Diff-Talk while this was open, so the record is AB-83/`AM-138`. Job 15's
  one changed screenshot (`ws-ask-conversation`) was read and adopted: the answer 32px lower
  for the action row, and no contract chat in the Ask rail. No migration, no new package.
  Checked: services active, `/health` 200, the card and paste handling in the live build, no
  page errors in a real browser.
- **Priyen's 8 Oct questions re-checked** (the 8 Oct answers gave the old SLA 10/25/50% and 30 days). On a
  local copy loaded with the same knowledge (Constitution L1.13, ratified standards, today's
  live SLA/TOS/AUP/Privacy pages) and the live code: early exit from an annual contract
  (full remaining value, §14), a 6-hour outage (99.17%, breached; Leapswitch 15%, CloudPe
  5%; 60 days), ₹14,500 a month (₹2,175 / ₹725) — all three correct. Production itself was
  not used: the agent's safety check blocks production reads.

## 2026-10-12

### Reached production

- **PR #170 (`4a774ed`) — the Ask page on assistant-ui**, laid out as its demo app (owner's
  choice). The deploy first refused the frontend (the new package not installed in the deploy
  tree; backend restarted, frontend untouched), then passed after `npm ci`. Checked: services
  active, `/login` 200, the new Ask chunks live, no page errors in a real browser.
- **PRs #171, #172, #173 (`70e62c4`), one deploy.** Ask uploads are the chat's material and a
  compliance question about them points to the Dashboard, on the agent path too (`AM-133`);
  each model reads its measured share of the material whole (Gemini 600k, DeepSeek 300k
  characters); a question up to 5,000 characters goes to the model whole, and a sent question can
  be edited in place, replacing it and every turn after it (`AM-134`). No migration, no new
  package. #173's first CI run was blocked by a stale `docs/api/openapi.json` (the new
  `edit_of` field); regenerated and re-run green. Checked: services active, `/login` 200, the
  edit control and the new wording in the live chunks, no page errors in a real browser.

### Production data operation (owner instruction: "give the fresh LegalMind")

- **~19:00 IST — every contract and Ask chat created before today deleted**, accounts untouched:
  45 contracts (with 42 Reviews, their versions and evidence), 79 chats, and 160 stored files —
  46 of the deleted versions and 114 orphans earlier contract deletions had left (`AM-55`'s delete
  never removed files). Done with the app's own deletes in one transaction after a dry run, each
  audited under the owner's account, `request_id` `ops-fresh-start-2026-10-12` (124 audit rows).
  0 Legal Decisions existed. Kept: all 13 accounts, the one chat created today.
- **Backups taken first**, root-only, in `/root/backups`:
  `legalmind-prod-before-fresh-2026-10-12.dump` (database) and
  `legalmind-documents-before-fresh-2026-10-12.tar.gz` (files). They hold real counterparty
  documents — delete them once nothing is needed back.

### Server

- **The root disk reached 100% (11 MB free) during a test run; now 50% (24 GB free).** Removed
  only recreatable data: six unused embedding/NLI models from the `AM-83` bake-off (production's
  three kept), the npm and apt caches, four VS Code server versions unused since September, and
  `node_modules`/build output in idle worktrees and in `/home/tasniya` (her code, uncommitted
  changes and account kept). Three demo servers (ports 3199, 3299, 8299) still run from deleted
  worktrees — memory only; left for the owner.

---

## 2026-10-09

### Reached production

- **12:24 IST — Ask hardening, PR #155 (`fe514f0`)**, deployed with PR #154. Migration
  `c2d7e4a9b1f6` (`assist.conversations.model`) applied; `alembic_version` checked afterwards.
- **14:28 IST — PRs #156 and #157 (`a37dd6a`).** Analysis asks its recognition calls together
  (a live MSA: upload → findings in 37 s, was 129 s). The header shows the Google profile photo
  (`AM-128`, session cookie only, nothing stored). The first deploy attempt failed while fetching
  Google Fonts during the build; the live site was untouched (staged build) and the re-run passed.
  CI job 12 failed once on #157 (kill-9 redelivery timing) and passed on re-run.

- **16:42 IST — Findings cards, PR #162 (`d68cd9a`).** The standard is always shown, a same-figure
  "Needs a decision" says why, basis codes read as words, finding explanations get their own
  rate limit (400/h). No migration (`alembic_version` still `c2d7e4a9b1f6`). Checked after deploy:
  services active, `/login` 200, the new card wording present in the live chunks. Existing reviews
  read correctly; the standard's VALUE on older MISSING/CONFLICT rows appears after a new upload.

- **17:42 IST — PR #166 (`45867fa`).** After an upload the Summary appears without a manual
  refresh: a "not started" Review is re-read for two minutes, so a just-queued analysis is seen
  (the queue leaves the Review UPLOADED until a worker picks it up). Frontend only. Checked:
  services active, `/login` 200, the new polling rule present in the live chunk.

### Left open

- DeepSeek's per-model time budget (owner decision D2); Gemini's own RECITATION refusal; one
  document whose Ask index was refused as `FABRICATED_TEXT` on 2026-10-08 (not investigated).

## 2026-09-29

### Reached production

- **`AM-109` and its addendum — Ask as a conversation.** PR #127, merge `7f0f96c`, deployed
  15:09 IST with `sudo legalmind-deploy` (backend, frontend, edge). No migration, no flag, no
  config change. CI 15/15 after adopting CI's two Ask visual baselines, inspected against
  expected first. Checked read-only afterwards: API, frontend and worker active; API health
  200; `/dashboard/ask` 200; no API errors after the restart.
- **Records PR #128** (`54e3b34`) — documents only, nothing to deploy; the deploy tree was
  fast-forwarded to it.

### Changed on the server, outside version control

- Nothing. `/root/.legalmind.env` unchanged since 2026-09-28.

### Open, and waiting on the owner

- `fix/ask-quote-open` (another session, 23 Sep) fixes the same fail-closed quote answer
  differently and now overlaps files `AM-109` changed; its owner should rebase it on `main` or
  close it.

### Worth knowing

- This log has no entries for 18–28 Sep, though several deploys happened then (`AM-94`–`AM-108`).
  They are recorded in [CHANGELOG.md](../../CHANGELOG.md) and
  [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md); not reconstructed here.

## 2026-09-17

### Reached production

| Merged | What | Deployed |
|---|---|---|
| #63 | The 2026-09-16 UX review: nine items | ✅ `97d440d` — deployed 11:14 by another session, not this one |

### In flight, and who holds it

**The cross-encoder reranker** is being merged, deployed and enabled by the session that built it,
on the owner's direct instruction to that session — **not by this one**. Recorded because the log
should say whose hands: if something is wrong with it tomorrow, it should be findable that they
were not mine. `LEGALMIND_RERANK` is enabled as its own env edit and its own restart, after the
deploy is verified, so a misbehaviour afterwards attributes to one change rather than two.

Measured twice, identical: hit@1 0.609 → 0.734, MRR 0.709 → 0.796, gold@3 0.797 → 0.844, recall
0.891 → 0.906, at +205 ms p50. **Wrongly-answered 1/13, user-visible wrong 0/13, false refusals 3,
faithfulness and citation precision 1.0 — all unchanged.** It reorders and does not change which
evidence reaches the model: retrieval truncates to `RETRIEVAL_TOP_K = 10` inside `search_hybrid`
before the reranker is reached, and nothing downstream drops a tail — verified in the live code
from this session rather than taken on report.

⚠️ `RERANK_CANDIDATES = 30` is the OFFLINE bakeoff's pool, not production's. Measured: 1 of 77
questions had the gate open with gold at rank 11–30, against 20 with gold present and the gate
shut. The deeper pool was tested and rejected on evidence.

**`LEGALMIND_POSITION_SYNTHESIS` (AM-67) is untouched and unrelated**, still waiting on the owner.
The two flags must not share a restart.

---

## 2026-09-16

### Reached production

| Merged | What | Deployed |
|---|---|---|
| #54 | `AM-70` — a client profile with no documents can be permanently deleted | ✅ `10113e0` |
| #55 | `AM-71` — a retired standard is no longer retrievable in Ask | ✅ `6c8af71` |
| #57 | Client Profiles: the page container is centred rather than hanging left | ✅ `bf7ec62` |
| #58 | Documentation of the developer deploy grant | ✅ `5c1d92c` |
| #59 | One deploy at a time (`flock` on `ops/deploy.sh`) | ✅ `8625f0a` |
| #62 | Client Profiles empty state: vertical rhythm and position | ✅ `4485174` |
| #64 | The quality gate was measuring a pipeline nobody ships | ✅ `c16cdaf` |
| #65 | A factual question was being answered with "run a Review" — comparison-intent routing | ✅ `be8d97c` |
| #66 | This file, plus the deploy rules in CLAUDE.md and a stale README claim | ✅ `b390bf7` |
| #67 | Add Client form redesign — **Tasniya's, and she did not choose the moment**; it had been merged since 13:48 and went out with the backend deploy below | ✅ `663971f` |
| #68 | Ask Phase 0 — citation numbers in the prose now match the citation list; per-stage timings; `AM-67` answers record their prompt version | ✅ `663971f` |

No migration was required by any of them. Services restarted clean each time — `NRestarts=0` on
`legalmind-api`, `legalmind-worker` and `legalmind-frontend`.

### Measured for the first time

Phase 0's instrumentation reported on its first live request after the restart:

```
assist.ask.timings   total 4783ms   rescue 4372ms   retrieval 8ms   positions 394ms
```

**The evidence-rescue step is 91% of that ask's latency**, and `assist.ask.rescued` remains **zero
in the entire journal** — the only rescue-judge call on record is a probe. So the feature costs one
extra provider call on roughly a third of questions, is the dominant cost of a request, and has not
yet changed a single answer a user saw.

Recorded as a **trade, not a verdict.** The ratified-set benchmark has it lifting recall 0.625 →
0.828 with wrongly-answered unchanged, and single-digit live traffic proves nothing against that.
The measurement that would settle it is what the rescue adds **on top of** a reranker once one
exists, not what it adds alone.

### Production data

**47 synthetic contracts deleted** — the C1–C5 generated test documents from the 2026-09-15
content-first contract run, with their 47 reviews and 1,066 findings. Deleted through the audited
`DELETE /contracts/{id}` path, so 47 `contract.deleted` audit events record it.

| | before | after |
|---|---|---|
| contracts | 94 | 47 |
| reviews | 90 | 43 |
| findings | 1,499 | 433 |
| document versions | 96 | 49 |
| configuration snapshots · legal decisions | 6 · 0 | 6 · 0 |

Verified before deleting: **zero legal decisions rested on any of them**. Verified after: no orphan
reviews, findings, document versions, evaluations, evidence rows or assist conversations, and every
remaining document version still has its file on disk. A verified `pg_dump` was taken first at
`/var/backups/legalmind/legalmind_v1_dev-20260916-1302-pre-synthetic-purge.dump`.

**Two documents under the same test account were NOT deleted, deliberately** — the executed
Leapswitch MSA and the Cubictree NDA are real counterparty material that happened to be uploaded
by the test account. Identification was by generated filename, not by account, precisely so that
the account's real uploads survived.

⚠️ **Deleting a contract does not delete its stored file.** 15 orphan blobs (~4 MB) remain in
`/var/lib/legalmind/documents` from this purge, alongside 60 that pre-date it. Invisible to the
dashboard, and left in place rather than cleaned up on an assumption.

### Changed on the server, outside version control

**The deploy tree is root-write-only.** `/root/Legalmind.v1` had **13,480 group-writable paths**,
`.git/config` among them. Group write was removed; group **read** is kept, so a developer can
still read the tree they deploy. This is not tidiness — see the grant below.

**`sudo legalmind-deploy`** — `/usr/local/sbin/legalmind-deploy` (root:root 0755) and
`/etc/sudoers.d/legalmind-deploy` (root:root 0440). Members of `legalmind-dev` may run that one
command as root, with **no arguments accepted**. It fast-forwards the deploy tree to `origin/main`
and runs `ops/deploy.sh`, refuses a dirty tree, and logs the invoking account to
`/var/log/legalmind-deploy.log`. Verified by running a real deploy as the unprivileged account, and
by confirming the same account is still refused `sudo bash`, `sudo systemctl`, `sudo id`,
`sudo legalmind-backup` and `legalmind-deploy` with any argument.

⚠️ **The two are one change, not two.** A deploy-only sudo rule is only deploy-only if what it
executes is root-writable. With `.git/config` group-writable, `core.hooksPath` alone would have
made `sudo legalmind-deploy` run arbitrary code as root. **Re-adding group write to the deploy
tree silently re-opens root.**

### Decided

- **Owner, 2026-09-16:** superseded/retired standards must not appear in normal Ask retrieval even
  when labelled "Superseded" — locked as `AM-71` (AB-23).
- **Owner, 2026-09-16:** a client profile with no documents may be permanently deleted — locked as
  `AM-70` (AB-22).
- **Owner, 2026-09-16:** a developer deploys their own merged work without an administrator
  present. Granted as the narrow sudo rule above.
- **`ops-publish@leapswitch.com` stays enabled.** Verified: role `DEPARTMENT_LEAD` only, no legal
  authority, and its entire history is 6 logins and the one `config.published` that put the 33
  standards live on 2026-09-15.

### Open, and waiting on the owner

- **The Gemini API key is NOT rotated, and there is a real exposure.** Four Turbopack build-cache
  files under `frontend/.next-e2e/cache/turbopack/` contain it at mode `664 root:legalmind-dev`,
  readable by a second local account — confirmed by reading them as that account, not inferred
  from the mode. Clean everywhere that matters more: all 3,095 git blobs including unreachable
  ones, the deployed bundle, `/var/log`, the journal, nginx and systemd config, and CI (which
  actively asserts no provider credential is present). The cache files are disposable.
- ~~PR #65 held on its branch~~ — **merged and deployed on the owner's go**, CI 27 pass / 0 fail.
  It was held deliberately until then: on this repository a merge now schedules a deploy, because
  the deploy command ships `origin/main`.
- **CI job 10 (Playwright) failed three times today**, each time the API process dying mid-run
  with `ECONNRESET` during document processing, no traceback, after 77–104 tests had already
  passed. A re-run of identical code passed every time.

  ⚠️ **The failure erases itself.** Re-running a job overwrites its conclusion, so job 10 now
  reports **18 success / 0 failures** across today's runs — including all three failures diagnosed
  by hand. That is why this has survived as "the known flake" rather than being fixed: no evidence
  accumulates, and each person who hits it sees a one-off. A process that dies leaving nothing in
  its own log is being killed from outside, most likely memory — not "Playwright is flaky".

- **`LEGALMIND_POSITION_SYNTHESIS` is NOT enabled.** `AM-67`'s r7 prerequisite was verified against
  the live corpus — **0 environment paths and 0 counterparty names** across all 40 position chunks,
  checked as two separate numbers because r7 names two kinds of locator. The flag is absent from
  `/root/.legalmind.env` and `config.py` defaults it to off, so this is a real state change
  awaiting the owner's word, not a formality.

- **The grounding floor is an undecided gap, not a defect.** `guardrails.verify_answer` grounds a
  sentence against the UNION of the content words of every chunk it cites, with a fixed
  `_GROUNDING_OVERLAP = 0.5`. A sentence can therefore pass while **no single cited clause supports
  it** — one measured case scores 0.42 against its own clause and passes only through the union —
  and the test weakens as the citation count rises, which the model itself chooses. Nothing in
  `docs/` or `all_lock.md` records this as a decision. Three candidate rules and the trade each
  makes are in ASK_AI_PROGRAMME.md; the choice is the owner's because it governs what Ask may
  assert.

- **Phase 1 (the query planner) is measured and does not earn its keep** — p50 4.7s → 10.6s,
  hit@1 flat, gold chunks reaching generation DOWN 0.407 → 0.358. PR #69 is presented to the owner
  as a choice: merge it disabled, or merge the measurement and park the feature.

### Worth knowing

**The deploy grant changed who bears the cost of a stale `main`.** `legalmind-deploy` ships
`origin/main`, so anything merged and not yet deployed goes out with the next person's unrelated
change — and that person is now a developer shipping a CSS fix, not an administrator. The habit
that keeps this safe is that **`main` holds only what you are willing to see deployed**.

---

## Before 2026-09-16

Not recorded here. This file starts on 2026-09-16; earlier history is in
[CHANGELOG.md](../../CHANGELOG.md) and the dated rows of
[LEGALMIND_PROJECT_STATE.md](LEGALMIND_PROJECT_STATE.md).

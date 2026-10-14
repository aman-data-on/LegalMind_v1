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

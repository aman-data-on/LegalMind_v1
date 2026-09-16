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

No migration was required by any of them. Services restarted clean each time — `NRestarts=0` on
`legalmind-api`, `legalmind-worker` and `legalmind-frontend`.

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
- **CI job 10 (Playwright) failed 2 of 4 runs**, each time the API process dying mid-run with
  `ECONNRESET` during document processing, no traceback. A re-run of identical code passed. A
  required check that fails half the time is one people learn to ignore.

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

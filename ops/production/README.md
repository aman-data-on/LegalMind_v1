# Production configuration — state, and what is still outstanding

**Last verified 2026-09-14** against `python3 -m legalmind.deploy.preflight` on the live
host. Build state stays [IMPLEMENTATION_STATUS.md](../../docs/00-project/IMPLEMENTATION_STATUS.md)'s
alone.

**Preflight: 17 PASS · 8 ATTEST · 0 FAIL · 0 BLOCKED** (was 11 PASS · 3 FAIL · 1 BLOCKED).
Every remaining row is an attestation about the platform that the application cannot
observe from inside itself.

## What the live service runs

`legalmind-api` (uvicorn) and `legalmind-worker` (Celery) from `/root/Legalmind.v1/backend`,
`legalmind-frontend` serving `.next` from the same tree, `nginx` terminating TLS,
`redis-server` as the broker, PostgreSQL 16 with pgvector. Environment for all three
LegalMind units comes from `/root/.legalmind.env` (mode 600).

## Applied 2026-09-14

| Change | Why | Verified by |
|---|---|---|
| `LEGALMIND_ENVIRONMENT=production` | The service declared none, so it ran as `development` while serving real legal documents. | `environment` PASS. No behaviour change: the only consumer is the `AM-31` egress gate, and it is RELEASED — checked before and after. |
| **Database credential rotated** and `LEGALMIND_DATABASE_URL` injected | The built-in development default was in use, carrying the `legalmind:legalmind` pair (S-6). | `secrets` PASS. New credential authenticates; **the old one is confirmed dead**; app reads 580 findings and 7,567 chunks. |
| **Role separation** — `legalmind_migrate` owns the schema, `legalmind` holds DML only | 55.2: the application role holds no DDL. Revoking `CREATE` alone would have been cosmetic — an owner keeps full rights over what it owns. | `database_roles` PASS. Rehearsed on a restored copy first: `SELECT`/`INSERT` work, `CREATE TABLE`, `DROP findings` and `ALTER findings` all refused, and the append-only audit trigger still refuses an `UPDATE`. |
| `legalmind_assist` role | `AM-25` r2 — enforced by the catalogue, not by convention. | `assist_role` PASS. `NOLOGIN`, so no credential exists. No `INSERT`/`UPDATE` on any of the ten authoritative tables. |
| **Worker + broker** | 55.1: analysis is a worker job, not inline in the request. | `analysis_worker` PASS. Worker installed and started **before** the broker URL was set. `inspect ping` answers; it consumes `analysis` and `assist`; a dispatched task was **transported through Redis and executed in the worker process** — it logged the request id. |
| **Five security headers** in nginx | All six were absent. | Live response carries HSTS, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy` — and `always` means they are present on error responses too, confirmed on a 405. |
| **Service isolation** on API and worker | Both ran as root with none. They parse attacker-supplied PDFs and shell out to OCR. | `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=full`, `PrivateDevices`, `MemoryMax=3G`, `TasksMax=512` — confirmed in force, and a real PDF still parses to 235 segments COMPLETE. |
| **Verified backup + nightly retention** | 55.2: "restore is verified, not assumed." | `backup_restore` PASS. A dump was restored into a scratch database and **12 tables matched row-for-row**. `/usr/local/sbin/legalmind-backup` runs 02:30 daily, verifies each archive, keeps 14 days; its log rotates weekly. |
| **Malware scanning: `accepted-absent`** | A decision 55.6 requires recorded either way. | `malware_scanning` PASS. Reasoning and residual risk below. |
| **Disk 85% → 67%** | 4.4 GB free was one incident from an outage. | 5 GB reclaimed from stale VS Code server versions, the npm cache and apt caches. Journal capped at 500 MB with 30-day retention (was 1.6 GB, uncapped). |

## The malware-scanning decision, and its residual risk

No scanner is installed. Installing ClamAV was assessed and **rejected on evidence**:

1. It adds a service outside the locked Step 39 stack — rule 19 puts that behind approval.
2. `freshclam` needs recurring outbound access, contradicting the locked egress allow-list
   where the API reaches exactly one endpoint and document-processing has no route out.
3. **Decisively, it does not address the actual threat.** Uploads are PDF/DOCX that are
   parsed by PyMuPDF and shelled out to tesseract, never executed and never served back as
   active content. The realistic attack is *parser exploitation*, which a signature scanner
   does not catch.

That threat was mitigated directly instead, the same day, with the service isolation above.

**Compensating controls, all verified:** content sniffed from magic bytes and required to
match the declared MIME; two accepted types only; a 25 MiB ceiling at both nginx and the
application; per-page parse containment; `nosniff`.

**Residual risk, stated plainly:** a document that exploits PyMuPDF or tesseract is not
detected before parsing. Isolation bounds the blast radius; it does not prevent the exploit.
**Follow-up:** scan at the storage or network boundary, where signature updates need no
egress from this host.

## Consequence for developers — read this before running the suite

The rotated credential means the built-in test default no longer authenticates, and the
production broker must not be visible to a test run. Both are correct, and both bite once:

```bash
set -a && . /root/.legalmind.env && set +a
unset LEGALMIND_BROKER_URL          # tests assume inline analysis; the worker uses a different DB
export LEGALMIND_TEST_DATABASE_URL="${LEGALMIND_DATABASE_URL/legalmind_v1_dev/legalmind_v1_test}"
export LEGALMIND_SOURCE_MATERIAL_DIR=/root/Legalmind.v1/legal-docs
python3 -m pytest tests -q
```

Verified 2026-09-14: **1,765 passed, 0 failed.**

## Backups and disaster recovery

Two copies with two different jobs. Run by `ops/production/backup.sh`, installed at
`/usr/local/sbin/legalmind-backup` and driven by root's cron at **02:30 daily**.

| | Local | Off-server |
|---|---|---|
| Location | `/var/backups/legalmind` (mode 700, dumps mode 600) | CloudPe Object Storage, bucket **`legalmind-production-backups`**, region **`S3-INWEST2`**, **private — public access denied** |
| Format | `pg_dump -Fc`, plaintext | the same dump, **GPG symmetric AES-256** before it leaves the host |
| Retention | **14 days** | **90 days** |
| Purpose | the fast path — one `pg_restore`, no key ceremony | the disaster path, for when this machine is what was lost |

**Why the local copy is not encrypted.** It is the copy you reach for at 3am, and hunting a
passphrase mid-outage turns a recovery into an incident. It sits at mode 600 in a mode-700
directory on a host where only root and postgres have accounts. The disk itself is **not**
encrypted — an outstanding provider attestation — which is precisely why the copy that *leaves*
the machine is encrypted first.

### Credentials and permissions

⚠️ **Paste the values with no leading space, and never `source` this file by hand.**
On 2026-09-15 a secret key was pasted as `LEGALMIND_S3_SECRET_ACCESS_KEY= <secret>` — one
leading space. Because `backup.sh` loaded the file with `.` (source), bash set the variable
empty and **ran the secret as a command**, printing it in the `command not found` error. The
credential leaked by being read, and was rotated.

`backup.sh` now **parses** the file instead: `KEY=VALUE`, surrounding whitespace and one layer
of quotes stripped, only `LEGALMIND_S3_*` and `LEGALMIND_BACKUP_*` exported, and **nothing
executed** — so a value containing `$(…)`, backticks, quotes or spaces is treated as the
arbitrary bytes a secret is. Pinned by `backend/tests/test_backup_credentials.py`, which also
fails the build if anyone reintroduces `source`.


`backup.sh` runs **as root** and drops to `postgres` only for `pg_dump`, so the credential file
stays root-only and postgres never reads it. Settings live in **`/root/.legalmind-backup.env`,
mode 600**, and are referenced by name only — never printed, never committed, never logged:

```
LEGALMIND_S3_ENDPOINT             # CloudPe S3 endpoint URL for the region
LEGALMIND_S3_BUCKET               # legalmind-production-backups
LEGALMIND_S3_REGION               # S3-INWEST2
LEGALMIND_S3_ACCESS_KEY_ID        # secret
LEGALMIND_S3_SECRET_ACCESS_KEY    # secret
LEGALMIND_BACKUP_PASSPHRASE_FILE  # path to a mode-600 file holding the GPG passphrase
```

The access key should be scoped to **this bucket only**, with just the operations the script
uses: `PutObject`, `GetObject`, `ListBucket`, `DeleteObject` (delete is required for the 90-day
prune, and for nothing else). It needs no bucket-creation, no policy and no ACL rights.

⚠️ **The GPG passphrase is a single point of failure.** Lose it and every off-server backup is
permanently unreadable — that is what "encrypted before upload" costs. It must live in the
owner's password manager, **off this machine**. A passphrase stored only beside the backups it
protects is not a second copy of anything.

**When the credential file is absent**, stage B is skipped and says so loudly on stderr and in
`/var/log/legalmind-backup.log`. Stage A still runs, so the local backup never depends on the
off-server configuration being present. A backup gap that logs nothing is indistinguishable
from a backup.

### What a run verifies

Stage A dumps, then proves the archive readable with `pg_restore -l` — a dump that cannot be
listed is not a backup. Stage B probes the bucket with a `HEAD` *before* encrypting (an expired
key should cost one request, not a full upload), encrypts, uploads with the SHA-256 stored in
object metadata so the checksum travels **with** the object, then **downloads it back**, compares
it byte-for-byte with what was sent, and **decrypts the read-back** to prove the key and cipher
work. Only then does it prune the remote by age.

Retention refuses to empty the bucket: if *every* object looks expired, the clock or the prefix
is wrong far more often than an entire archive genuinely aged out overnight, and deleting the lot
is not the recovery from either. Pinned by `backend/tests/test_backup_retention.py`.

### Restoring

```bash
# 1 — off-server: list, fetch, decrypt
set -a && . /root/.legalmind-backup.env && set +a
python3 /root/Legalmind.v1/ops/production/s3_object.py list legalmind_v1_dev/
python3 /root/Legalmind.v1/ops/production/s3_object.py get <key> /tmp/restore.dump.gpg
gpg --batch --decrypt --passphrase-file "$LEGALMIND_BACKUP_PASSPHRASE_FILE" \
    --output /tmp/restore.dump /tmp/restore.dump.gpg

# 1' — local: skip straight to step 2 with a file from /var/backups/legalmind

# 2 — restore into a NON-PRODUCTION database first, always
su -s /bin/bash postgres -c "createdb legalmind_restore_test"
su -s /bin/bash postgres -c "pg_restore -d legalmind_restore_test --no-owner --role=postgres /tmp/restore.dump"

# 3 — prove it before trusting it, then drop the scratch copy
su -s /bin/bash postgres -c "psql -d legalmind_restore_test -c 'select count(*) from findings'"
su -s /bin/bash postgres -c "dropdb legalmind_restore_test"
```

Restoring **over** production is a deliberate act: stop `legalmind-api` and `legalmind-worker`
first, take a fresh dump of what you are about to replace, then `pg_restore --clean`.

### Verified 2026-09-14

Exercised end to end on this host, production untouched throughout:

| Step | Result |
|---|---|
| Local dump + `pg_restore -l` | **PASS** — 8 dumps retained, none deleted |
| GPG AES-256 encryption | **PASS** — `PGP symmetric key encrypted data - AES with 256-bit key`, ciphertext does not begin `PGDMP` |
| SHA-256 integrity | **PASS** — decrypted output byte-identical to the source dump |
| Restore into `legalmind_restore_test` | **PASS** — 32 requirements / 580 findings / 58 reviews / 3 snapshots / 1,578 audit events, **identical to production**; 49 tables both; alembic `e9f2b6c4a173` |
| Local retention | **PASS** — 15- and 40-day files pruned, 1/5/13-day kept |
| Remote retention guard | **PASS** — 7 unit tests, including refusal to delete every object |
| Credential handling | **PASS** — a missing-credential error names the *variables*, never a value |
| **Upload / download to CloudPe** | **NOT RUN — credentials not yet supplied.** This is the one untested stage. |

## Outstanding — and who has to act

### Requires the infrastructure owner, not this host

* **Egress allow-list** (ATTEST — measured 2026-09-14, and a packet filter cannot express
  it). Current posture: `ufw` is active but **inbound-only**; `iptables -S OUTPUT` shows
  policy `ACCEPT`, so there is no outbound restriction at all. The obvious remedy —
  deny-by-default with an IP allow-list — was measured and rejected on evidence:
  `generativelanguage.googleapis.com` resolves across Google's shared, rotating front-end
  ranges (`172.217.x` among others), the same infrastructure that serves `drive.google.com`
  and Gmail. An address-based rule therefore **cannot distinguish the one permitted
  destination from the exfiltration paths it exists to block**, and would additionally break
  OIDC login and certificate renewal unpredictably as those addresses rotate. It would be an
  allow-list in name only.

  Satisfying `AM-30` t8 as written needs a **hostname-aware forward proxy** with `CONNECT`
  restricted to `generativelanguage.googleapis.com:443`, the services pointed at it, and
  direct egress denied. That is a new service, so rule 19 puts it to the owner rather than to
  a session. Until then the honest statement is: egress is unrestricted at the network layer,
  and the compensating controls are the single code-level egress seam (`AM-30`, enforced by
  `test_import_boundaries.py`) and the systemd isolation applied to both services.
* **Encryption at rest** (ATTEST). A platform property of the volume.
* **TLS confirmation** (ATTEST). The certificate, redirect, TLS 1.2/1.3-only posture and
  `certbot.timer` are all verified here; what cannot be observed from inside is whether the
  database connection is encrypted where the network is not fully trusted.
* **CloudPe credentials for off-server backups** (2026-09-14). The backup system is **built,
  installed and tested** — encryption, integrity, decrypt, restore-to-scratch-database and
  retention all verified on this host. The only untested stage is the network one, because
  **no credentials exist anywhere**: not in `/root/.legalmind.env`, no `~/.aws`, no `~/.s3cfg`,
  and the bucket name appears nowhere in the repository. Supply the five values named under
  *Credentials and permissions* above in `/root/.legalmind-backup.env` (mode 600) plus a
  passphrase file, and the nightly job starts uploading with no code change. Until then every
  backup still exists only on the machine it protects, and each run says so on stderr.

### Requires an owner decision — configuration, not infrastructure

* **`verify_terminology` fails for the six reconciled standards, and has since AB-14.**
  CI runs this tool, but source documents are gitignored and absent there, so 32 of 40
  standards SKIP and the job is green on eight. Run where the documents live — apparently
  for the first time, on 2026-09-14 — it reports **34 PASS · 6 FAIL · 0 SKIP**, and the
  identical six fail on `main`, so this is **pre-existing and not a release regression**.

  The six failures are exactly the six standards carrying `_reconciliation` — the set AB-14
  / `AM-43` reconciled to the Legal Constitution. The tool reproduces a standard from its
  `source_file`, which for these six is the LeapSwitch document they were *originally*
  ratified from, and those documents now state the **superseded** position by design: TOS §7
  still says 5% per month where the ratified position is the Constitution's 2%; MSA §17.2
  still says six months of affected-service fees where the position is twelve months of
  total fees. So the check measures the wrong source for them and can only fail.

  Pointing those six at their Constitution section instead was tried and measured: it fixes
  `LIABILITY-MSA-001` cleanly (Constitution §9 reproduces 12 MONTHS / `FEES_PAID`) but leaves
  five failing differently — four `UNRESOLVED` because their mapping terminology was tuned to
  contract-clause wording and does not match the Constitution's prose statement of a
  position, and one basis mismatch. **The change was reverted rather than shipped**: neither
  source verifies a reconciled standard on its own, retuning legal matching terminology
  changes analysis behaviour, and it is not a release blocker. It needs a ruling on what a
  reconciled standard should reproduce from, and the retune belongs with the 35.10
  calibration against representative counterparty paper.

  No production impact: these standards match real contract clauses correctly, which is what
  the engine actually does with them, and the 580 live findings exercise that path.

### Requires a decision, then a maintenance window

* **The deployment lives under `/root`.** That is why `ProtectHome` cannot be set and why
  both services still run as root. Relocating to `/opt/legalmind` with a dedicated
  `legalmind` system user is the real fix; it is a planned migration, not a live edit.
* **The production database is named `legalmind_v1_dev`.** Cosmetic, required by no locked
  decision, and a rename is a live-data operation.
* **Content-Security-Policy.** Deliberately not set: Next.js ships an inline bootstrap
  script, so a correct policy needs per-request nonces from the application, and a wrong
  one breaks the app silently. The next security step, and a code change rather than a
  config one.
* **pgvector 0.6.0 → 0.8.0+** before relying on an ANN index over a large pre-filtered set.
* **Rate limiting is in-process**, correct for a single worker only. A multi-worker
  deployment needs the shared Redis behind it — Redis is now running, so this is a small
  change when a second worker appears.

## Deploying AB-20 — COMPLETE (code 2026-09-14, standards published 2026-09-15)

**Status: DONE.** Code deployed 2026-09-14 (PR #36,
`a1b23e1d5277ea2f43b794a039d8e13cdd45d21e`). Standards imported and published **2026-09-15**:
snapshot `5c85b87c`, **33 ACTIVE / 7 DEPRECATED**, published by `aman.singh@leapswitch.com`.
Findings and reviews unchanged at 580 / 58; the seven retired were refused entry to the snapshot.

The procedure below is kept as the runbook for the next configuration release — both findings it
records were confirmed true in the live run.

They are deliberately left as **one atomic operator step**. Publishing writes `actor_id` into
the append-only audit trail, no API token is stored, and locked **55.3** makes creating a
production credential "a deliberate operator act" — `tools/dev_account.py` refuses on production
for exactly that reason. Forging a token with the signing secret would circumvent that lock and
record an action against a person who did not perform it, so it is not done. Running the import
alone would also leave production half-applied: eight inert `DRAFT` standards and seven newly
deprecated ones, with no new snapshot.

**The two commands, in order** (both run by an operator; the second needs a session for an
account holding `configuration.publish`):

```bash
# 1 — import (writes requirement versions; creates the 8 new ones as DRAFT)
cd /root/Legalmind.v1/backend
set -a && . /root/.legalmind.env && set +a
python3 -m tools.import_ratified_standards --actor-email <you@leapswitch.com>

# 2 — regenerate and validate the payload, then publish exactly 33
python3 -m tools.publish_payload -o /root/publish-33.json
curl -sS -X POST https://legalmind.lsnw.io/api/v1/configuration/publish \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  --data @/root/publish-33.json
```

`tools/publish_payload.py` derives the list from the ratified files and **refuses** unless it is
exactly 33 publishable and 7 retired, with no overlap and no duplicates — so the payload cannot
drift from the directory. Never hand-edit it, and never send the 40-code list the import tool
prints.

Rehearsed in full against `legalmind_dryrun`, a scratch database restored from
`legalmind_v1_dev-20260914-2110-pre-ab20-deployment.dump`. Two findings below would each
have broken the deployment if it had been run from the obvious reading of the tooling.

**The database needs no migration.** `alembic_version` is already at head `e9f2b6c4a173`,
in both `main` and the release branch. There is no migration step.

**Order.** Back up → merge to `main` → `git pull` in `/root/Legalmind.v1` → restart
`legalmind-api` and `legalmind-worker` → import → publish → smoke test.

### Finding 1 — the import leaves eight standards inert

`import_ratified_standards.py` creates a Requirement that did not exist before with status
`DRAFT`, not `ACTIVE`. Publishing pins only `ACTIVE`, so **importing alone ships nothing
new**. In the rehearsal that left 25 ACTIVE / 8 DRAFT / 7 DEPRECATED — and the eight inert
ones include `SERVICE-DISCONTINUATION-MSA-001`, the compound requirement `AM-66` exists to
deliver. `POST /configuration/publish` promotes the codes it is given from DRAFT to ACTIVE,
which is what makes them effective. 25 + 8 = the 33 active standards.

### Finding 2 — the list the tool prints will be REFUSED

The import tool ends by naming **all 40 codes** for publication. Publishing a retired code
raises `BusinessRuleRejected` (`AM-65`: reversing a retirement is an owner decision, not a
publish call), so pasting that list fails the whole call. Publish **these 33 only**:

```
ARBITRATION-MSA-001,ARBITRATION-TOS-001,AUTORENEW-MSA-001,AUTORENEW-TOS-001,
CHANGE-OF-CONTROL-NOTICE-MSA-001,CLAIM-WINDOW-SLA-001,CONF-SURVIVAL-MSA-001,
CONF-SURVIVAL-NDA-001,CONVENIENCE-NOTICE-MSA-001,CURE-PERIOD-MSA-001,DATA-PURGE-MSA-001,
DATA-RETRIEVAL-TOS-001,DISPUTE-WINDOW-MSA-001,EARLY-TERM-RESTRICTION-MSA-001,
GOVLAW-MSA-001,GOVLAW-NDA-001,GOVLAW-TOS-001,GST-EXCLUSIVE-MSA-001,INDEMNITY-MSA-001,
IP-OWNERSHIP-MSA-001,KYC-RETENTION-TOS-001,LATE-FEE-TOS-001,LIAB-EXCLUSIONS-MSA-001,
LIABILITY-MSA-001,LIABILITY-TOS-001,NON-SOLICIT-NDA-001,PAYMENT-PERIOD-MSA-001,
PRICE-CHANGE-NOTICE-MSA-001,RESIDUALS-NDA-001,SERVICE-DISCONTINUATION-MSA-001,
SUSPENSION-NOTICE-CURE-MSA-001,TERM-NOTICE-NDA-001,TRADE-SECRET-CARVEOUT-NDA-001
```

Never publish these seven — the call is refused by design:
`COMPELLED-DISCLOSURE-NDA-001`, `FORCE-MAJEURE-MSA-001`, `FORCE-MAJEURE-TOS-001`,
`LIAB-CARVEOUTS-MSA-001`, `RETURN-DESTRUCTION-MSA-001`, `RETURN-DESTRUCTION-NDA-001`,
`WARRANTY-DISCLAIMER-MSA-001`.

Publishing is a Legal-permission action (`CONFIGURATION_PUBLISH`) and is audited. The
import tool deliberately will not do it, `--publish` notwithstanding — that flag only
prints the request.

### What existing data does

Nothing is rewritten. The rehearsal ended with **580 findings and 58 reviews unchanged**;
each stays pinned to the snapshot it ran under (rule 16). The **152 findings that cite one
of the seven retired standards** keep their evidence and render as *"Retired — not present
in the current Constitution"*, read from the requirement's current status. **No Legal
Decision exists** anywhere in the database, so no human ruling is disturbed by any of this.

### Rollback

Restore the pre-deployment dump and check out the previous `main` commit. Snapshots are
append-only, so rolling back configuration is a restore, never a delete.

## Files and rollback

| Artifact | Purpose |
|---|---|
| `/root/.legalmind.env` | Live configuration, mode 600. Backups: `.bak-2026-09-14`, `.bak-pre-dbcred-*`. |
| `/root/nginx-legalmind.bak-*` | nginx config before the headers were added. |
| `/var/backups/legalmind/*.dump` | Verified dumps, mode 600, 14-day retention. |
| `ops/production/role_sep.sql` · `role_sep_rollback.sql` | The role separation and its reversal. |
| `ops/production/legalmind-worker.service` | The worker unit, installed at `/etc/systemd/system/`. |
| `/etc/systemd/system/legalmind-{api,worker}.service.d/10-hardening.conf` | Service isolation. Delete and `daemon-reload` to revert. |

**One correction worth recording.** `REASSIGN OWNED` also moves *shared* objects, so it
reassigned all 21 `legalmind*` databases cluster-wide, not just the production one's
objects. Production was and is correct; the test and scratch databases lost rights their
tooling expects, which surfaced as a failing suite. Ownership of every non-production
database was returned to `legalmind` and the suite passes. Anyone repeating this should
scope it deliberately.

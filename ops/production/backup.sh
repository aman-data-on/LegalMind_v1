#!/usr/bin/env bash
# Nightly verified backup, local and off-server — locked 55.2 ("restore is
# verified, not assumed").
#
# STAGE A (always): dump, prove the archive is readable, prune by age.
# STAGE B (when configured): encrypt, upload off-server, read it back, prune.
#
# Retention is two different jobs, deliberately:
#   LOCAL   14 days, unencrypted, mode 600 in a mode-700 directory — the FAST
#           recovery path. Restoring is one pg_restore with no key ceremony.
#   REMOTE  90 days, encrypted — the DISASTER path, for when this machine is
#           the thing that was lost.
#
# WHY THE LOCAL COPY IS NOT ENCRYPTED. It is the copy you reach for at 3am, and
# hunting a passphrase mid-outage turns a recovery into an incident. It sits at
# mode 600 in a mode-700 directory on a host where only root and postgres have
# accounts. The disk itself is NOT encrypted — an outstanding provider
# attestation (see README.md), and exactly why the copy that LEAVES this
# machine is encrypted before it goes.
#
# RUNS AS ROOT and drops to postgres only for pg_dump, so the credential file
# stays root-only and postgres never reads it.
set -euo pipefail

DB=legalmind_v1_dev
OUT=/var/backups/legalmind
LOCAL_KEEP_DAYS=14
REMOTE_KEEP_DAYS=90
CREDS=/root/.legalmind-backup.env
HELPER="$(dirname "$(readlink -f "$0")")/s3_object.py"
STAMP=$(date +%Y%m%d-%H%M)
F="$OUT/$DB-$STAMP.dump"

if [ "$(id -u)" -ne 0 ]; then
    echo "must run as root (it drops to postgres for pg_dump)" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Stage A — the local backup. Must work even if every off-server setting is
# missing, so nothing below this block may fail it.
# ---------------------------------------------------------------------------
mkdir -p "$OUT"; chmod 700 "$OUT"; chown postgres:postgres "$OUT"
su -s /bin/bash postgres -c "pg_dump -Fc -d '$DB' -f '$F'"
chmod 600 "$F"

# A dump that cannot be listed is not a backup. Fail loudly rather than leaving
# a corrupt file to be discovered on the day it is needed.
if ! su -s /bin/bash postgres -c "pg_restore -l '$F'" >/dev/null 2>&1; then
    echo "BACKUP FAILED verification: $F" >&2
    exit 1
fi

find "$OUT" -name "$DB-*.dump" -type f -mtime +$LOCAL_KEEP_DAYS -delete
echo "local ok: $F ($(du -h "$F" | cut -f1)); $(ls -1 "$OUT"/$DB-*.dump | wc -l) retained"

# ---------------------------------------------------------------------------
# Stage B — off-server. Skipped LOUDLY rather than silently: a backup gap that
# logs nothing is indistinguishable from a backup.
# ---------------------------------------------------------------------------
if [ ! -f "$CREDS" ]; then
    echo "OFF-SERVER UPLOAD SKIPPED: $CREDS is absent — this backup exists only" \
         "on the machine it protects. See ops/production/README.md." >&2
    exit 0
fi

# Parse, never `source`. Sourcing a credentials file EXECUTES it as root, so a
# stray character turns a secret into a command: on 2026-09-15 a key pasted as
# `KEY= <secret>` — one leading space — made bash set the variable empty and run
# the secret as a command, printing it in the "command not found" error. The
# credential leaked into a terminal log by being read.
#
# So: read KEY=VALUE lines, strip surrounding whitespace and one layer of
# quotes, export nothing else, and execute nothing. Values may contain spaces,
# `$`, backticks and quotes without consequence, which is the point — a secret
# is arbitrary bytes, not shell.
while IFS= read -r _line || [ -n "$_line" ]; do
    case "$_line" in ''|'#'*) continue ;; esac
    [ "${_line#*=}" = "$_line" ] && continue          # no '=' — not a setting
    _key="${_line%%=*}"
    _val="${_line#*=}"
    _key="${_key#"${_key%%[![:space:]]*}"}"; _key="${_key%"${_key##*[![:space:]]}"}"
    _val="${_val#"${_val%%[![:space:]]*}"}"; _val="${_val%"${_val##*[![:space:]]}"}"
    case "$_val" in
        \"*\") _val="${_val#\"}"; _val="${_val%\"}" ;;
        \'*\') _val="${_val#\'}"; _val="${_val%\'}" ;;
    esac
    case "$_key" in
        LEGALMIND_S3_*|LEGALMIND_BACKUP_*) export "$_key=$_val" ;;
        *) echo "ignoring unexpected setting in $CREDS: $_key" >&2 ;;
    esac
done < "$CREDS"
unset _line _key _val

: "${LEGALMIND_BACKUP_PASSPHRASE_FILE:?set LEGALMIND_BACKUP_PASSPHRASE_FILE in $CREDS}"
if [ ! -r "$LEGALMIND_BACKUP_PASSPHRASE_FILE" ]; then
    echo "OFF-SERVER UPLOAD FAILED: passphrase file unreadable" >&2
    exit 1
fi

# Probe before doing work. An expired key should cost one HEAD request, not a
# full encrypt-and-upload that fails at the last step.
python3 "$HELPER" check

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
ENC="$WORK/$(basename "$F").gpg"

# Encrypted BEFORE it leaves the machine: encryption at rest at the provider is
# unconfirmed, and would be their control rather than ours even if it were not.
gpg --batch --quiet --yes --symmetric --cipher-algo AES256 \
    --passphrase-file "$LEGALMIND_BACKUP_PASSPHRASE_FILE" \
    --output "$ENC" "$F"

KEY="$DB/$(basename "$ENC")"
python3 "$HELPER" put "$ENC" "$KEY"

# Read it back. An upload that cannot be downloaded, or that does not match
# what was sent, is not a backup — and fetching it is the only way to know.
BACK="$WORK/readback.gpg"
python3 "$HELPER" get "$KEY" "$BACK"
if ! cmp -s "$ENC" "$BACK"; then
    echo "OFF-SERVER VERIFY FAILED: read-back differs from what was uploaded" >&2
    exit 1
fi

# And prove the ciphertext still decrypts, so a key or cipher mistake surfaces
# now rather than during a restore. To /dev/null: correctness, not content.
if ! gpg --batch --quiet --yes --decrypt \
        --passphrase-file "$LEGALMIND_BACKUP_PASSPHRASE_FILE" \
        --output /dev/null "$BACK" 2>/dev/null; then
    echo "OFF-SERVER VERIFY FAILED: read-back does not decrypt" >&2
    exit 1
fi

python3 "$HELPER" prune "$DB/" "$REMOTE_KEEP_DAYS"
echo "off-server ok: $KEY (encrypted, uploaded, read back, decrypts)"

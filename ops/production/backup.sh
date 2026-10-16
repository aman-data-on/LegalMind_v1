#!/usr/bin/env bash
# Nightly verified backup, local and off-server — locked 55.2 ("restore is
# verified, not assumed").
#
# STAGE A (always): dump, prove the archive is readable, prune by age.
# STAGE C1 (always): archive the uploaded documents, prove every file is intact.
# STAGE B (when configured): encrypt, upload off-server, read it back, prune.
# STAGE C2 (when configured): the same for the documents archive.
#
# The documents were not backed up at all until 2026-10-16: the original files
# live in LEGALMIND_STORAGE_ROOT, outside the database, and a database restore
# without them restores references to files that no longer exist.
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
LOCAL_KEEP_DAYS=14
REMOTE_KEEP_DAYS=90
HELPER="$(dirname "$(readlink -f "$0")")/s3_object.py"
STAMP=$(date +%Y%m%d-%H%M)
# Overridable ONLY to validate this script without touching the real backups: a
# separate local directory and a remote prefix of its own (a validation run puts
# everything under `$REMOTE_ROOT`, so the 90-day prune can never reach the real
# archive). Read here, before the credential file is parsed, so that file cannot
# move them. Cron sets none of these; the defaults are production.
OUT="${LEGALMIND_BACKUP_DIR:-/var/backups/legalmind}"
CREDS="${LEGALMIND_BACKUP_CREDS:-/root/.legalmind-backup.env}"
DOCS="${LEGALMIND_BACKUP_DOCUMENTS_DIR:-/var/lib/legalmind/documents}"
REMOTE_ROOT="${LEGALMIND_BACKUP_REMOTE_ROOT:-}"
F="$OUT/$DB-$STAMP.dump"
DOCS_STATUS=0

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
# Stage C1 — the uploaded documents, archived locally. Taken AFTER the dump, so
# every file the dump refers to is already on disk (a file is written before its
# row is committed, and the store is write-once). A failure here is reported and
# the run exits non-zero at the end, but never stops the database's off-server
# copy below: one broken stage must not cost the other its backup.
# ---------------------------------------------------------------------------
# >>> documents-archive
# The store is content-addressed: a file is named `<sha256 of its bytes>-<n>.<ext>`
# (`legalmind.ingestion.storage`), so every file can PROVE it is intact. One that
# does not hash to its own name is corruption, reported now, not on restore day.
documents_archive() {
    local src="$1" dest="$2" listed hashed bad=0 name sum
    if [ ! -d "$src" ]; then
        echo "DOCUMENTS BACKUP FAILED: $src does not exist" >&2
        return 1
    fi
    listed=$(find "$src" -type f | wc -l)
    # Fourteen nightly archives live beside the dumps on the root disk. Refuse to
    # write one unless the store's size plus 1 GiB stays free, so a growing store
    # fails this stage loudly instead of filling the disk the database runs on.
    local need avail
    need=$(( $(du -sb "$src" | cut -f1) + 1073741824 ))
    avail=$(df --output=avail -B1 "$(dirname "$dest")" | tail -1 | tr -d ' ')
    if [ "$avail" -lt "$need" ]; then
        echo "DOCUMENTS BACKUP FAILED: $avail bytes free, $need needed in $(dirname "$dest")" >&2
        return 1
    fi
    while IFS= read -r -d '' name; do
        sum=$(basename "$name"); sum="${sum%%-*}"
        if [[ "$sum" =~ ^[0-9a-f]{64}$ ]] && \
           [ "$(sha256sum "$name" | cut -c1-64)" != "$sum" ]; then
            echo "DOCUMENTS BACKUP FAILED: $name does not hash to its own name" >&2
            bad=1
        fi
    done < <(find "$src" -type f -print0)
    [ "$bad" -eq 0 ] || return 1
    (umask 077 && tar -C "$src" -cf "$dest" .) || {
        echo "DOCUMENTS BACKUP FAILED: could not write $dest" >&2; return 1; }
    hashed=$(tar -tf "$dest" | grep -vc '/$' || true)
    if [ "$hashed" -ne "$listed" ]; then
        echo "DOCUMENTS BACKUP FAILED: $dest holds $hashed files, the store $listed" >&2
        return 1
    fi
    echo "documents ok: $dest ($listed files, $(du -h "$dest" | cut -f1))"
}
# <<< documents-archive
D="$OUT/documents-$STAMP.tar"
if documents_archive "$DOCS" "$D"; then
    find "$OUT" -name "documents-*.tar" -type f -mtime +$LOCAL_KEEP_DAYS -delete
else
    DOCS_STATUS=1
    D=""
fi

# ---------------------------------------------------------------------------
# Stage B — off-server. Skipped LOUDLY rather than silently: a backup gap that
# logs nothing is indistinguishable from a backup.
# ---------------------------------------------------------------------------
if [ ! -f "$CREDS" ]; then
    echo "OFF-SERVER UPLOAD SKIPPED: $CREDS is absent — this backup exists only" \
         "on the machine it protects. See ops/production/README.md." >&2
    exit "${DOCS_STATUS:-0}"
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

# The file can exist and still not be filled in — the template ships with
# PASTE_* placeholders. Treat that as "not configured yet", exactly like a
# missing file, rather than sending the placeholder to the provider as a
# credential and failing the nightly job with a 403 traceback every night.
case "${LEGALMIND_S3_ACCESS_KEY_ID:-}${LEGALMIND_S3_SECRET_ACCESS_KEY:-}" in
    *PASTE_*|"")
        echo "OFF-SERVER UPLOAD SKIPPED: $CREDS still has placeholder credentials —" \
             "this backup exists only on the machine it protects." >&2
        exit "${DOCS_STATUS:-0}"
        ;;
esac

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

# >>> offsite
# One file off the server: encrypted BEFORE it leaves the machine (encryption at
# rest at the provider is unconfirmed, and would be their control rather than
# ours even if it were not), uploaded, READ BACK and compared byte for byte (an
# upload that cannot be downloaded, or does not match, is not a backup), and the
# read-back decrypted (a key or cipher mistake surfaces now, not during a
# restore). Then the prefix is pruned by age. `$3`, when given, checks what the
# decrypted read-back holds — the documents archive's file listing.
offsite() {
    local src="$1" prefix="$2" check="${3:-}" enc back plain=/dev/null
    [ -z "$check" ] || plain="$WORK/plain"
    enc="$WORK/$(basename "$src").gpg"
    back="$WORK/readback-$(basename "$src").gpg"
    # every step fails explicitly: called as `offsite … || DOCS_STATUS=1`, bash
    # suspends `set -e` inside the function, and a failed upload must not run on
    gpg --batch --quiet --yes --symmetric --cipher-algo AES256 \
        --passphrase-file "$LEGALMIND_BACKUP_PASSPHRASE_FILE" \
        --output "$enc" "$src" || {
        echo "OFF-SERVER UPLOAD FAILED: could not encrypt $src" >&2; return 1; }
    python3 "$HELPER" put "$enc" "$prefix$(basename "$enc")" || {
        echo "OFF-SERVER UPLOAD FAILED: upload to $prefix failed" >&2; return 1; }
    python3 "$HELPER" get "$prefix$(basename "$enc")" "$back" || {
        echo "OFF-SERVER VERIFY FAILED: read-back of $prefix could not be fetched" >&2
        return 1; }
    if ! cmp -s "$enc" "$back"; then
        echo "OFF-SERVER VERIFY FAILED: read-back of $prefix differs from what was uploaded" >&2
        return 1
    fi
    # decrypted to /dev/null unless its contents are checked: no plaintext copy of
    # the database is ever written by this step
    if ! gpg --batch --quiet --yes --decrypt \
            --passphrase-file "$LEGALMIND_BACKUP_PASSPHRASE_FILE" \
            --output "$plain" "$back" 2>/dev/null; then
        echo "OFF-SERVER VERIFY FAILED: read-back of $prefix does not decrypt" >&2
        return 1
    fi
    if [ -n "$check" ] && ! "$check" "$plain" "$src"; then
        echo "OFF-SERVER VERIFY FAILED: read-back of $prefix does not hold what was archived" >&2
        return 1
    fi
    [ -z "$check" ] || rm -f "$plain"
    python3 "$HELPER" prune "$prefix" "$REMOTE_KEEP_DAYS" || {
        echo "OFF-SERVER RETENTION FAILED: prune of $prefix failed" >&2; return 1; }
    echo "off-server ok: $prefix$(basename "$enc") (encrypted, uploaded, read back, decrypts)"
}
# the decrypted documents archive lists the same files as the one archived
same_listing() { [ "$(tar -tf "$1" | sort)" = "$(tar -tf "$2" | sort)" ]; }
# <<< offsite

offsite "$F" "$REMOTE_ROOT$DB/"

# Stage C2 — the documents archive, under its own prefix and retention.
if [ -n "$D" ]; then
    offsite "$D" "${REMOTE_ROOT}documents/" same_listing || DOCS_STATUS=1
fi
exit "$DOCS_STATUS"

#!/usr/bin/env bash
# Nightly verified backup with retention — locked 55.2 ("restore is verified, not
# assumed"). Dumps, proves the archive is readable, then prunes by age.
#
# Retention: 14 daily copies on this host. That is a RECOVERY window, not an
# archive — the legal record's durability comes from the database and the
# append-only audit trail, not from these files. Off-host copies are still
# outstanding: a backup that only exists on the machine it protects is not a
# backup against losing that machine.
set -euo pipefail

DB=legalmind_v1_dev
OUT=/var/backups/legalmind
KEEP_DAYS=14
STAMP=$(date +%Y%m%d-%H%M)
F="$OUT/$DB-$STAMP.dump"

mkdir -p "$OUT"; chmod 700 "$OUT"
pg_dump -Fc -d "$DB" -f "$F"
chmod 600 "$F"

# A dump that cannot be listed is not a backup. Fail loudly rather than leaving a
# corrupt file to be discovered on the day it is needed.
if ! pg_restore -l "$F" >/dev/null 2>&1; then
    echo "BACKUP FAILED verification: $F" >&2
    exit 1
fi

find "$OUT" -name "$DB-*.dump" -type f -mtime +$KEEP_DAYS -delete
echo "backup ok: $F ($(du -h "$F" | cut -f1)); $(ls -1 "$OUT"/$DB-*.dump | wc -l) retained"

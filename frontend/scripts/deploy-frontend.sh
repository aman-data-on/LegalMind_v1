#!/usr/bin/env bash
#
# Atomic frontend deploy — build, verify, swap, restart, roll back on failure.
#
# WHY THIS EXISTS. The systemd unit `legalmind-frontend` serves `.next` directly
# from this working tree, and `next build` deletes and rewrites that directory in
# place. On 2026-09-01 a build that failed partway (a type error in an unrelated
# route) left the live site with no BUILD_ID and a half-written chunk set: every
# page hung on "Loading…" while nginx still returned 200, so nothing looked down
# until someone opened a browser.
#
# The fix is to make the swap atomic. A failed build now touches nothing the
# running process can see.
#
# Usage:  bash scripts/deploy-frontend.sh
set -euo pipefail

cd "$(dirname "$0")/.."

STAGING=".next-staging"
PREVIOUS=".next-previous"
SERVICE="legalmind-frontend"
PROBE="https://legalmind.lsnw.io/login"

say() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }

# ---------------------------------------------------------------------------
# The API must not be OLDER than the backend source (2026-09-02).
#
# WHY. The API rejects any request field it does not recognise
# (schemas.Body: extra="forbid" — deliberate, and not to be weakened). So a
# frontend built from source that sends a newly-added field, deployed against an
# API process still running yesterday's code, fails validation outright: on
# 2026-09-02 every Ask question returned "The request could not be validated."
# until `systemctl restart legalmind-api` ran. This script restarts only the
# frontend, so it must refuse to ship a frontend ahead of the API.
#
# The check is local and cheap: if any backend source file is newer than the
# running API process, the API has not loaded the code the frontend was built
# against. `scripts/deploy.sh` deploys both in dependency order and never trips
# this. Frontend-only work never touches backend/ and passes untouched.
# ---------------------------------------------------------------------------
if [[ "${LEGALMIND_ALLOW_STALE_API:-0}" != "1" ]]; then
  api_started="$(systemctl show legalmind-api -p ActiveEnterTimestamp --value 2>/dev/null || true)"
  if [[ -n "$api_started" && "$api_started" != "n/a" ]]; then
    api_epoch="$(date -d "$api_started" +%s)"
    newest_src="$(find ../backend/legalmind ../backend/alembic -name '*.py' -printf '%T@\n' 2>/dev/null | sort -rn | head -1 | cut -d. -f1)"
    if [[ -n "$newest_src" && "$newest_src" -gt "$api_epoch" ]]; then
      echo "REFUSING: backend source is newer than the running legalmind-api process." >&2
      echo "  API started:        $api_started" >&2
      echo "  newest backend .py: $(date -d "@$newest_src")" >&2
      echo "Deploy both in order:   bash scripts/deploy.sh" >&2
      echo "Or restart the API:     systemctl restart legalmind-api   (then re-run this script)" >&2
      echo "Frontend-only change against an intentionally old API: LEGALMIND_ALLOW_STALE_API=1" >&2
      exit 1
    fi
  fi
fi

# ---------------------------------------------------------------------------
# The tree must not carry someone else's work in progress (2026-09-04).
#
# WHY. The systemd units serve straight from this ONE working tree, which more
# than one session edits at a time. So a deploy ships whatever is in the tree at
# that instant — including changes that are mid-review and not approved. That
# happened today: a frontend deploy at 13:34 shipped another session's
# uncommitted Reviews/Report work, and the owner met it live before approving
# it. (The same shared tree also cost a session its unstaged files earlier the
# same day, from the opposite direction.)
#
# A deploy should ship a COMMIT, not a desk. Committed work is reviewable,
# attributable and revertable; a dirty tree is none of those. Scoped to the
# source that actually reaches a build or the API process, so untracked scratch
# and staging dirs never trip it.
# ---------------------------------------------------------------------------
if [[ "${LEGALMIND_ALLOW_DIRTY_TREE:-0}" != "1" ]]; then
  dirty="$(git status --porcelain -- src public package.json next.config.ts ../backend/legalmind 2>/dev/null || true)"
  if [[ -n "$dirty" ]]; then
    echo "REFUSING: the working tree has uncommitted changes that this deploy would ship." >&2
    echo "$dirty" >&2
    echo "Another session may be mid-task in this same tree — a deploy ships a commit, not a desk." >&2
    echo "Commit your own files by explicit path, then re-run this script." >&2
    echo "Deliberately shipping the tree as-is: LEGALMIND_ALLOW_DIRTY_TREE=1" >&2
    exit 1
  fi
fi

say "Type-checking before building — a build is not the place to find a type error"
npx tsc --noEmit

say "Building into $STAGING (the live $PWD/.next is untouched until this succeeds)"
rm -rf "$STAGING"
LEGALMIND_NEXT_DIST="$STAGING" npx next build

# A build can exit 0 and still be unusable; BUILD_ID is the file the server needs.
if [[ ! -f "$STAGING/BUILD_ID" ]]; then
  echo "REFUSING TO DEPLOY: $STAGING/BUILD_ID is missing after a successful build." >&2
  exit 1
fi
say "Build produced BUILD_ID $(cat "$STAGING/BUILD_ID")"

say "Swapping into place"
rm -rf "$PREVIOUS"
[[ -d .next ]] && mv .next "$PREVIOUS"
mv "$STAGING" .next

say "Restarting $SERVICE"
systemctl restart "$SERVICE"
sleep 5

code="$(curl -s -o /dev/null -w '%{http_code}' "$PROBE" || true)"
if [[ "$code" != "200" ]]; then
  say "Probe returned $code — ROLLING BACK to the previous build"
  rm -rf .next
  [[ -d "$PREVIOUS" ]] && mv "$PREVIOUS" .next
  systemctl restart "$SERVICE"
  sleep 5
  echo "Rolled back. Probe now: $(curl -s -o /dev/null -w '%{http_code}' "$PROBE" || true)" >&2
  exit 1
fi

say "Deployed. $PROBE -> $code. Previous build kept in $PREVIOUS"

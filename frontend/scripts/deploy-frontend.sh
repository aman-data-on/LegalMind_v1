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
#         bash scripts/deploy-frontend.sh --preflight   (the checks only — ops/deploy.sh
#         runs them before it migrates or restarts anything, review 2026-10-14)
set -euo pipefail

cd "$(dirname "$0")/.."
PREFLIGHT=$([[ "${1:-}" == "--preflight" ]] && echo 1 || echo 0)

# The deploy lock (ops/deploy-lock.sh): `npm run deploy` during a full deploy built
# into the same staging directory — the mixed build the lock exists to prevent
# (review, 2026-10-14). Under ops/deploy.sh the lock is inherited, never re-taken.
# shellcheck source=ops/deploy-lock.sh
. ../ops/deploy-lock.sh
deploy_lock

STAGING=".next-staging"
PREVIOUS=".next-previous"
SERVICE="legalmind-frontend"
PROBE="https://legalmind.lsnw.io/login"

say() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }

# ---------------------------------------------------------------------------
# node_modules must match package-lock.json (2026-09-11).
#
# WHY. This script builds but has never installed, which was invisible while the
# dependency list sat unchanged for weeks. Stage 2 added tailwindcss and
# @tailwindcss/postcss, and `postcss.config.mjs` requires the latter at build
# time: deploying onto a tree whose node_modules predates the merge fails in the
# PostCSS transform of `globals.css` — a stack trace about a stylesheet that did
# not change, which is a genuinely confusing place to start debugging.
#
# The atomic swap means a failed build ships nothing, so this is not a safety
# fix; it is a "fail with the right sentence" fix. It refuses rather than
# installing on your behalf, because pulling packages is not what someone typing
# `npm run deploy` asked for.
# ---------------------------------------------------------------------------
# A package that is present but at the WRONG VERSION is just as stale (2026-10-13):
# the Next.js 16.3.4 -> 16.3.8 security fix deployed "successfully" while the server
# kept running 16.3.4, because only presence was checked. npm records the installed
# tree in node_modules/.package-lock.json; every package the lockfile names must be
# there at the lockfile's version, transitive ones included (sharp and source-map-js
# moved in that same fix). An optional package for another platform may be absent.
stale_deps=$(node -e '
  const fs = require("fs");
  const want = require("./package-lock.json").packages || {};
  let have = {};
  try { have = JSON.parse(fs.readFileSync("node_modules/.package-lock.json", "utf8")).packages || {}; } catch {}
  const out = [];
  for (const [path, w] of Object.entries(want)) {
    if (!path || w.link) continue;
    const h = have[path];
    if (!h) { if (!w.optional) out.push(path.replace(/^.*node_modules\//, "") + " (missing)"); continue; }
    if (h.version !== w.version) out.push(path.replace(/^.*node_modules\//, "") + " " + h.version + " -> " + w.version);
  }
  process.stdout.write(out.slice(0, 10).join(", ") + (out.length > 10 ? ", ..." : ""));
')
if [ -n "$stale_deps" ]; then
  printf '\n\033[1;31m==> node_modules does not match package-lock.json: %s\033[0m\n' "$stale_deps"
  printf '    an administrator must run (the deploy tree is root-write-only, so a\n'
  printf '    legalmind-dev account cannot):\n\n'
  printf '      (cd %s && npm install --no-audit --no-fund)\n\n' "$(pwd)"
  printf '    (`npm install`, not `npm ci`, on a live tree: npm ci deletes node_modules\n'
  printf '     first, and the running server loads modules from it.)\n\n'
  exit 1
fi

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
# Not in --preflight: then the API has not been restarted YET, by design.
if [[ "${LEGALMIND_ALLOW_STALE_API:-0}" != "1" && "$PREFLIGHT" != "1" ]]; then
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

if [[ "${LEGALMIND_FRONTEND_PREFLIGHT_DONE:-0}" != "1" ]]; then   # done once per deploy
  say "Type-checking before building — a build is not the place to find a type error"
  npx tsc --noEmit
fi
[[ "$PREFLIGHT" == "1" ]] && exit 0

say "Building into $STAGING (the live $PWD/.next is untouched until this succeeds)"
rm -rf "$STAGING"
LEGALMIND_NEXT_DIST="$STAGING" npx next build

# A build can exit 0 and still be unusable; BUILD_ID is the file the server needs.
if [[ ! -f "$STAGING/BUILD_ID" ]]; then
  echo "REFUSING TO DEPLOY: $STAGING/BUILD_ID is missing after a successful build." >&2
  exit 1
fi
say "Build produced BUILD_ID $(cat "$STAGING/BUILD_ID")"

# QA-006 (2026-10-29): the build inherited the deploy's umask and the tree's setgid
# legalmind-dev group, so 596 files of the code a root server runs were writable by every
# developer. Only the deployer writes the live build; refuse to ship one anyone else can.
chmod -R go-w "$STAGING"
if [[ -n "$(find "$STAGING" -perm /022 -print -quit)" ]]; then
  echo "REFUSING TO DEPLOY: $STAGING still has group- or world-writable files." >&2
  exit 1
fi

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

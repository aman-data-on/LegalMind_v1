# shellcheck shell=bash
# ONE DEPLOY AT A TIME — sourced by ops/deploy.sh and frontend/scripts/deploy-frontend.sh;
# `sudo legalmind-deploy` (ops/production/legalmind-deploy) takes the same lock inline.
#
# Two overlapping deploys are not a slow deploy, they are a broken one: both build the
# frontend into the same staging directory and both swap it into place, so what ends up
# live is a mixture of two builds and the `.next-previous` rollback copy points at
# neither. Backend-side, two `alembic upgrade head` runs race on the version table.
# Fail rather than queue — a deploy that waits silently looks hung.
#
# A script started by a deploy that ALREADY holds the lock inherits its descriptor,
# named in LEGALMIND_DEPLOY_LOCK_FD. flock(2) belongs to the open file, so re-locking
# that same descriptor succeeds where opening the file afresh would refuse — the
# wrapper → deploy.sh → deploy-frontend.sh chain neither deadlocks nor refuses itself
# (review, 2026-10-14). The descriptor must really be the lock file: a stray variable
# pointing anywhere else is ignored, and the lock is taken as usual.
DEPLOY_LOCK=/var/lock/legalmind-deploy.lock

deploy_lock() {
  local fd="${LEGALMIND_DEPLOY_LOCK_FD:-}"
  if [[ "$fd" =~ ^[0-9]+$ ]] && [ "/proc/self/fd/$fd" -ef "$DEPLOY_LOCK" ] \
      && flock -n "$fd"; then
    return 0
  fi
  exec {fd}> "$DEPLOY_LOCK"
  if ! flock -n "$fd"; then
    echo "REFUSING: another deploy is already running ($DEPLOY_LOCK)." >&2
    echo "Wait for it to finish, then run this again." >&2
    exit 1
  fi
  export LEGALMIND_DEPLOY_LOCK_FD="$fd"
}

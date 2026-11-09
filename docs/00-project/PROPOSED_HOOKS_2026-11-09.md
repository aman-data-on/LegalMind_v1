# Proposed hooks and permission rules — 2026-11-09

**Status: 📁 PROPOSAL — NOT ENABLED.** Nothing here is active. Enabling it means creating the
files below in the repo and merging them; from then on they bind **every** Claude Code session in
this repository, including sessions already running in other worktrees once they pick up the
change. That is why the owner decides, and why it was not switched on during the restructure
([AGENT_INSTRUCTIONS_AUDIT_2026-11-09.md](AGENT_INSTRUCTIONS_AUDIT_2026-11-09.md) finding 30).

**Why hooks.** Official guidance (code.claude.com/docs/en/best-practices): *"If something has to
happen every time, make it a hook, a deny rule, or a managed setting. CLAUDE.md is for guidelines,
and Claude is allowed to decide a guideline doesn't apply."* and *"a hook is for a rule with zero
exceptions … keep the enforced set small."* A `PreToolUse` command hook reads the tool call as JSON
on stdin; exit 2 blocks it and stderr goes back to Claude; a JSON `permissionDecision: "ask"` shows
the normal permission prompt (code.claude.com/docs/en/hooks-guide). Hooks and ask/deny rules run
before auto mode's classifier, so they hold in every permission mode.

## What is enforced, and why each has zero exceptions

| # | Rule | Source | Mechanism | Effect |
|---|---|---|---|---|
| 1 | `all_lock.md` is append-only | CLAUDE.md rule 22; CI job 6 catches it only after push | `guard-all-lock.py` (Edit/Write) + `guard-bash.sh` (`sed -i`, `>`, `truncate`) | block |
| 2 | Never `git add -A` / `git add .` | shared trees hold other sessions' files | `guard-bash.sh` | block |
| 3 | No commit / push / PR without the owner; CLM branches may commit, push and open DRAFT PRs | owner 2026-09-29; CLM delegation 2026-11-04 | `guard-bash.sh` checks the branch | ask (prompt) |
| 4 | No merge, `gh pr merge` or `sudo legalmind-deploy` without the owner | owner 2026-09-29; merge gate AGENTS.md §13a | `guard-bash.sh` | ask (prompt) |
| 5 | No `reset --hard`, `clean -f`, `checkout -- `, `restore .`, `stash` (except `list`/`show`), `worktree remove --force` | 2026-09-04 incident: unrecoverable loss of another session's work | `guard-bash.sh` | block |
| 6 | No `--update-snapshots` | visual baselines are CI-cut only | `guard-bash.sh` | block |
| 7 | No `e2e_bootstrap --recreate` on a curated/shared DB; the e2e suite only with `LEGALMIND_E2E_DATABASE_URL` set inline | 2026-11-06 wipe of `legalmind_clm_e2e` | `guard-bash.sh` | block |
| 8 | No writes (`curl` POST/PUT/PATCH/DELETE/data) to production `:8000`/`:3000` | production safety | `guard-bash.sh` | block |
| — | No bare `next build` in the deploy tree | 2026-09-01 outage | **already enforced in code**: `frontend/next.config.ts` phase guard + `scripts/guard-build-target.mjs` | no hook needed |

**Recommended first five** if the owner wants a smaller start: 1, 2, 5, 7, 3 (in that order —
the first four only block things that have already destroyed work).

**Known limits.** A regex hook reads the command text, so an obfuscated command (a script file,
`eval`, variables) can pass it; it is a seatbelt against mistakes, not a security boundary. Rule 3
reads the branch from the hook's `cwd`; a `cd other-tree && git commit` is judged by the session's
directory. In a non-interactive session an "ask" cannot be answered and so behaves as a refusal —
which is the intended result for an unattended agent outside the CLM branches.

## 1. `.claude/settings.json` (proposed)

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/guard-bash.sh", "onFailure": "block" }
        ]
      },
      {
        "matcher": "Edit|Write",
        "hooks": [
          { "type": "command", "command": "python3 -I \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/guard-all-lock.py", "onFailure": "block" }
        ]
      }
    ]
  }
}
```

`onFailure: "block"` (best-practices § Enforce steps with hooks) stops the action if the guard
itself crashes. Requires `jq` (present at `/usr/bin/jq`).

## 2. `.claude/hooks/guard-bash.sh` (proposed)

```bash
#!/usr/bin/env bash
# PreToolUse(Bash) guard for LegalMind. Exit 2 = block (stderr goes back to Claude);
# a JSON "ask" decision shows the owner the normal permission prompt.
input=$(cat)
cmd=$(jq -r '.tool_input.command // ""' <<<"$input")
cwd=$(jq -r '.cwd // "."' <<<"$input")
block() { echo "BLOCKED by .claude/hooks/guard-bash.sh: $1" >&2; exit 2; }
ask() { jq -n --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$r}}'; exit 0; }
re() { grep -Eq -- "$1" <<<"$cmd"; }

re 'git[[:space:]]+add[[:space:]]+(-A|--all|\.)([[:space:]]|$)' && block "stage by explicit path, never 'git add -A' / 'git add .' (CLAUDE.md § Git)"
re 'git[[:space:]]+(reset[[:space:]]+--hard|clean[[:space:]]+-[a-zA-Z]*f|checkout[[:space:]]+--[[:space:]]|restore[[:space:]]+\.|stash([[:space:]]+(push|save|clear|drop|pop)|[[:space:]]*$|[[:space:]]+-))' \
  && block "destroys other sessions' uncommitted work; use your own worktree (AGENTS.md §7)"
re 'git[[:space:]]+worktree[[:space:]]+remove[[:space:]].*--force' && block "never force-remove a worktree (AGENTS.md § Shared working tree)"
re '--update-snapshots' && block "visual baselines are CI-cut only; adopt CI's baselines"
re '(sed|perl)[[:space:]]+-i[^|;&]*all_lock\.md|(^|[^>])>[[:space:]]*[^>|;&]*all_lock\.md|truncate[^|;&]*all_lock\.md' \
  && block "all_lock.md is append-only (rule 22); append with '>>' only"
re 'e2e_bootstrap.*--recreate|--recreate.*e2e_bootstrap' && re 'legalmind_clm_(e2e|demo)|legalmind_v1_tier2_gate|legalmind_prod' \
  && block "--recreate on a curated/shared DB; name your own scratch DB (skill local-stack)"
re 'test:e2e|playwright[[:space:]]+test' && ! re 'LEGALMIND_E2E_DATABASE_URL=' \
  && block "the e2e suite recreates LEGALMIND_E2E_DATABASE_URL; set it inline to your own DB"
re 'curl[^|;&]*(-X[[:space:]]*(POST|PUT|PATCH|DELETE)|--data|-d[[:space:]])[^|;&]*(127\.0\.0\.1|localhost):(8000|3000)([^0-9]|$)|curl[^|;&]*(127\.0\.0\.1|localhost):(8000|3000)[^|;&]*(-X[[:space:]]*(POST|PUT|PATCH|DELETE)|--data|-d[[:space:]])' \
  && block "never write to production (:8000/:3000)"

# Owner's go needed (2026-09-29).
re 'sudo[[:space:]]+legalmind-deploy|gh[[:space:]]+pr[[:space:]]+merge|git[[:space:]]+merge[[:space:]]' && ask "merge/deploy needs the owner's explicit go"
if re 'git[[:space:]]+(commit|push)([[:space:]]|$)|gh[[:space:]]+pr[[:space:]]+(create|edit|ready)'; then
  branch=$(git -C "$cwd" branch --show-current 2>/dev/null)
  # CLM delegation (owner 2026-11-04): commit, push and DRAFT PRs on the CLM branches.
  if [[ "$branch" =~ ^(feat/clm-|records/clm-|research/clm-) ]] && ! re 'gh[[:space:]]+pr[[:space:]]+ready'; then exit 0; fi
  ask "commit/push/PR needs the owner's explicit go (branch: ${branch:-unknown})"
fi
exit 0
```

## 3. `.claude/hooks/guard-all-lock.py` (proposed)

```python
#!/usr/bin/env python3
"""PreToolUse(Edit|Write) guard: all_lock.md accepts appends only (CLAUDE.md rule 22)."""
import json, pathlib, sys
data = json.load(sys.stdin)
ti = data.get("tool_input", {})
path = pathlib.Path(ti.get("file_path", ""))
if path.name != "all_lock.md":
    sys.exit(0)
def block(why):
    print(f"BLOCKED by .claude/hooks/guard-all-lock.py: all_lock.md is append-only (rule 22) — {why}", file=sys.stderr)
    sys.exit(2)
if data.get("tool_name") == "Write":
    block("Write replaces the file; append with Edit at the end or `cat >> all_lock.md`")
old, new = ti.get("old_string", ""), ti.get("new_string", "")
if ti.get("replace_all"):
    block("replace_all edits existing lines")
text = path.read_text(encoding="utf-8") if path.is_file() else ""
if not (old and new.startswith(old) and text.rstrip("\n").endswith(old.rstrip("\n"))):
    block("an Edit must match the file's last lines and only add text after them")
sys.exit(0)
```

An Edit to `all_lock.md` passes only when `old_string` is the file's last lines and `new_string`
starts with it (a pure append). Write and `replace_all` are always blocked.

## 4. How to test before and after enabling

Before enabling (no effect on any session): save the two scripts and this self-check, then run it.
Measured 2026-11-09: **36/36 pass** for `guard-bash.sh`; **5/5** for `guard-all-lock.py`
(append allowed; middle edit, rewrite of the last line, Write blocked; other files untouched).

```bash
#!/usr/bin/env bash
# Self-check for guard-bash.sh: expected exit code / decision per command.
cd "$(dirname "$0")"
W=/root/legalmind-worktrees/agent-docs-20261109
C=/root/legalmind-worktrees/clm-p1
fail=0
t() {  # want(block|ask|none) cwd command
  local out r d
  out=$(jq -n --arg c "$3" --arg d "$2" '{cwd:$d,tool_input:{command:$c}}' | bash guard-bash.sh 2>/dev/null); r=$?
  d=none; [ "$r" = 2 ] && d=block
  [ -n "$out" ] && d=$(jq -r '.hookSpecificOutput.permissionDecision' <<<"$out")
  if [ "$d" = "$1" ]; then echo "ok    $d  $3"; else echo "FAIL  got $d want $1: $3"; fail=1; fi
}
t block $W 'git add -A'; t block $W 'git add .'; t none $W 'git add backend/x.py ./CLAUDE.md'
t block $W 'git reset --hard origin/main'; t block $W 'git clean -fd'; t block $W 'git checkout -- .'
t none $W 'git checkout -b feat/x'; t block $W 'git stash'; t block $W 'git stash push -u'; t none $W 'git stash list'
t block $W 'git worktree remove --force /x'; t none $W 'git worktree remove /x'
t block $W 'npx playwright test --update-snapshots'
t block $W "sed -i 's/a/b/' all_lock.md"; t block $W 'echo x > all_lock.md'; t none $W 'cat rec.md >> all_lock.md'; t none $W 'wc -l all_lock.md'
t block $W 'LEGALMIND_DATABASE_URL=postgresql://u@h/legalmind_clm_e2e python3 -m tools.e2e_bootstrap --recreate'
t none  $W 'LEGALMIND_DATABASE_URL=postgresql://u@h/legalmind_mytask python3 -m tools.e2e_bootstrap --recreate'
t block $W 'npm run test:e2e'; t none $W 'LEGALMIND_E2E_DATABASE_URL=postgresql://u@h/legalmind_mine npm run test:e2e'
t block $W 'curl -X POST http://127.0.0.1:8000/api/v1/x'; t none $W 'curl -s http://127.0.0.1:8000/health'
t none  $W 'curl -X POST http://127.0.0.1:8399/api/v1/x'; t block $W 'curl -s -d a=1 localhost:3000/login'
t ask $W 'git commit -m x'; t ask $W 'git push origin HEAD'; t ask $W 'gh pr create --draft'
t none $C 'git commit -m x'; t none $C 'git push origin feat/clm-p1-negotiate'; t ask $C 'gh pr ready 287'
t ask $C 'gh pr merge 287'; t ask $W 'git merge origin/main'; t ask $W 'sudo legalmind-deploy'
t none $W 'git log --oneline -3'; t none $W 'git status'
exit $fail
```

After enabling: in a scratch worktree ask Claude to run `git add -A` (expect the BLOCKED message),
to `git commit` on a non-CLM branch (expect a permission prompt), and to edit a middle line of
`all_lock.md` (expect the block). `/hooks` lists what is active.

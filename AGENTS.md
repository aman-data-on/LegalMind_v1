# Agent instructions

**Read [CLAUDE.md](CLAUDE.md) before doing anything in this repository.** It is the single authoritative instruction file for every AI coding agent working here, regardless of vendor. This file exists only so agents that look for `AGENTS.md` find their way there.

Nothing is duplicated here — duplicated rules drift.

Minimum context before you act:

| | |
|---|---|
| The rules | [CLAUDE.md](CLAUDE.md) |
| Where everything lives | [docs/README.md](docs/README.md) |
| What is settled | [docs/00-project/LOCKED_DECISIONS.md](docs/00-project/LOCKED_DECISIONS.md) |
| What is *not* settled | [docs/00-project/IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) |
| How to propose a change | [CONTRIBUTING.md](CONTRIBUTING.md) |
| How to work here, day to day | [docs/00-project/CLAUDE_WORKING_RULES.md](docs/00-project/CLAUDE_WORKING_RULES.md) |

**LegalMind is a specification-first project, and implementation is authorized and underway** — `IMPL-01` (2026-08-17) for the V1 engine, `IMPL-02` (2026-08-25) for the assist lane. *(This paragraph previously said the project was "in the specification phase" and that application code must not be written; that was true when written and became misleading once `IMPL-01` landed. Corrected 2026-08-25.)*

**Specification-first still governs everything.** Authorization covers **building what is already locked** and confers no authority to decide what is not. Do not implement an unspecified behavior, add a table, column or enum not covered by a lock record, or add a technology or dependency without approval. Do not invent a legal rule, threshold, or evaluator behavior. When you find a contradiction, report it — never resolve it yourself.

---

# Multi-Agent and Multi-User Development Rules

**Owner instruction, 2026-09-18 — this is the FINAL flow for every git and GitHub
operation, confirmed by the owner. There is no other procedure and no per-session
variation.** Mandatory for every coding agent, developer and automated session working in
this repository. They govern **git and GitHub operations** —
branching, worktrees, commits, pushes, PRs, conflicts, CI. They do not touch the legal
specification rules in [CLAUDE.md](CLAUDE.md), which still win on anything about what may
be built or decided.

**CLAUDE.md and this file agree** (reconciled 2026-11-09): work on a task branch in your
own worktree, always; `main` is branch-protected. Claude Code loads `CLAUDE.md` only, not
this file (code.claude.com/docs/en/memory § AGENTS.md), so CLAUDE.md § Git carries the
essentials and links here for the procedure. Still standing from the 2026-09-02 owner
instruction: merge promptly and delete the branch, no retry branches (`-work`, `-work2`),
the deploy tree is `/root/Legalmind.v1` on clean `main`, one deploy at a time.

The goal is to prevent:
- Multiple sessions editing the same worktree
- Branch checkout conflicts
- Accidental commits to `main`
- Merge and rebase conflicts
- CI failures caused by stale branches
- Overlapping changes from multiple agents
- Lost uncommitted work
- Unclear ownership of files
- Test and specification changes without authorization

---

## 1. Never work directly on `main`

Do not edit, commit, merge, or rebase while working on `main`.

Before changing files, verify:

```bash
git branch --show-current
git status --short
```

The current branch must be a dedicated task branch.

If currently on `main`, create or switch to a task branch:

```bash
git fetch origin
git switch -c <type>/<short-task-name> origin/main
```

Allowed branch prefixes:

```text
feat/   new functionality
fix/    bug fix
refactor/  internal refactor
test/   test-only changes
docs/   documentation-only changes
chore/  maintenance
```

Examples:

```text
feat/partner-agreement-positions
fix/ask-document-type-routing
test/generation-feel
docs/update-agent-rules
```

Never use a generic branch such as:

```text
work
test
changes
temp
my-branch
```

---

## 2. One branch must belong to one worktree

A Git branch cannot be checked out in two worktrees at the same time.

Before checking out a branch, run:

```bash
git worktree list
```

If the branch is already assigned to another worktree, do not check it out again.

Instead, use the existing worktree:

```bash
cd /path/to/existing/worktree
git status
```

Create a new worktree for a new task:

```bash
git fetch origin
git worktree add ../worktrees/<task-name> -b <type>/<short-task-name> origin/main
cd ../worktrees/<task-name>
```

Each session must use a separate worktree.

Never use the same worktree for:
- Two agents
- Two users
- Two coding sessions
- A coding agent and manual edits at the same time

Before starting work, record:

```text
Agent:
User:
Task:
Branch:
Worktree:
Files owned:
Started:
```

---

## 3. Inspect before editing

At the beginning of every session:

```bash
git status
git branch --show-current
git log -5 --oneline
git fetch origin
```

Then inspect:
- The current branch
- Uncommitted changes
- Existing work in the target files
- Recent commits
- Open PR status, if applicable
- CI status, if applicable

Never overwrite existing uncommitted changes without explicit confirmation.

If unrelated changes are present, stop and report:

```text
I found pre-existing changes in:
- file 1
- file 2

I will not modify or discard them without approval.
```

---

## 4. Pull before starting work

Before editing a task branch:

```bash
git fetch origin
git rebase origin/main
```

If the branch is shared by multiple people, do not rebase it without agreement. Use a merge instead:

```bash
git fetch origin
git merge origin/main
```

For a personal branch, prefer:

```bash
git rebase origin/main
```

Never run this from the wrong branch:

```bash
git pull origin <other-branch>
```

Always verify the current branch first:

```bash
git branch --show-current
```

---

## 5. Keep changes small and focused

Each branch must address one task.

Do not mix:
- Feature work and unrelated refactoring
- Backend changes and unrelated frontend cleanup
- Test rewrites and production changes unrelated to those tests
- Formatting changes across the repository
- Dependency upgrades with feature work
- Specification changes with ordinary bug fixes

Avoid changing the same files as another active task whenever possible.

If two tasks require the same file, coordinate ownership before editing.

---

## 6. File ownership and coordination

Before editing a shared or high-risk file, search for active work:

```bash
git log --all --oneline -- path/to/file
git diff origin/main...HEAD -- path/to/file
```

High-risk files include:
- Database models
- Migrations
- Shared configuration
- API schemas
- Type registries
- CI workflows
- Lock/specification files
- Shared frontend vocabulary
- Dependency files
- Generated files

If another agent is working on the same file, do not silently edit it.

Coordinate one of these options:

1. One agent owns the file and the other provides a patch.
2. Split the work into separate sections.
3. Sequence the work so one branch lands first.
4. Create a smaller follow-up PR.

---

## 7. Never discard unknown work

Do not run these commands unless the owner explicitly authorizes data loss:

```bash
git reset --hard
git clean -fd
git checkout -- .
git restore .
git stash / git stash clear
```

If you need a clean state, do **not** stash, back up or commit someone else's changes
(stash and `add -A` sweep in other sessions' files; commits need the owner, §13). Create
your own worktree at `origin/main` instead (§2) and leave the unknown work where it is;
report it if it blocks you. To tell your failures from pre-existing ones, run the same
tests in a clean worktree at `origin/main` and compare.

Before using `git stash pop`, inspect:

```bash
git stash list
git stash show --stat stash@{0}
```

---

## 8. Commit checkpoints regularly — once the owner has said "commit"

No commit without the owner's go (§13, owner 2026-09-29; CLM branches delegated 2026-11-04).
When committing is authorized, make small, understandable commits.

Good commit examples:

```text
Add Partner Agreement document type
Add regression test for Partner Agreement retrieval
Fix readable document type rendering
Update frontend document type vocabulary
```

Avoid commits such as:

```text
changes
fix
updates
final
try again
```

Before committing:

```bash
git status
git diff --check
git diff --stat
git diff
```

Commit only files belonging to the current task:

```bash
git add path/to/file1 path/to/file2
git commit -m "Add regression test for document type routing"
```

Never use:

```bash
git add .
```

unless every changed file has been reviewed and belongs to the task.

---

## 9. Do not modify tests only to make CI pass

Tests represent behavior and specification.

Do not:
- Weaken an assertion without understanding its purpose
- Delete a failing test
- Change expected counts casually
- Convert a meaningful test into an empty test
- Skip a test to hide a failure
- Change fixtures without documenting the specification change

If expected behavior changes, update all of these as appropriate:
- Production code
- Tests
- Fixtures
- Documentation
- Changelog
- Specification or lock records
- PR description

If a repository CI rule requires a label for specification changes, add the required label to the PR.

---

## 10. Run the narrowest tests first

After changing code, run focused tests first.

Examples:

```bash
pytest backend/tests/test_specific_feature.py
pytest backend/tests/test_specific_feature.py -q
npm test -- path/to/test.ts
npm run typecheck
ruff check .
mypy .
```

Then run the complete required checks before pushing.

Use the repository's documented commands. If no commands are documented, inspect:

```text
README.md
CONTRIBUTING.md
pyproject.toml
package.json
Makefile
.github/workflows/
```

Never claim tests passed unless they were actually run.

Report skipped or unavailable checks honestly:

```text
Passed:
- backend focused tests

Not run:
- frontend typecheck because Node dependencies are not installed
- integration tests because Docker is unavailable
```

---

## 11. CI failure investigation

When CI fails, do not rerun blindly.

Identify:
1. The exact failed job
2. The first meaningful failure
3. Whether it is caused by code, configuration, environment, or stale branch state
4. Whether the failure is expected negative-test output
5. Whether the failure is unrelated to the current change

Use the job log and find the final failure summary.

Common categories:

```text
merge conflict:
  branch is stale or overlapping changes exist

specification-change failure:
  expected outputs changed without required approval/label

typecheck failure:
  frontend/backend vocabulary or API types are inconsistent

test failure:
  behavior regression or incorrect fixture

database failure:
  migration, schema, fixture, or test isolation problem

security scan failure:
  dependency or container vulnerability

environment failure:
  missing service, database, model, secret, or dependency
```

Do not declare CI fixed until the actual failed job passes.

### A "failing" check that failed nothing

A job whose annotation reads `Canceling since a higher priority waiting request
for ci-<branch> exists` did not fail — it was cancelled as a superseded
duplicate, and GitHub counts `cancelled` as not-success. §13a below covers how
to attribute a row to its run; this is how to clear one that is blocking a
merge.

Rerun the one job, not the suite:

```bash
gh run list --branch <branch> --limit 4 --json databaseId,event,status
gh run view <run-id> --json jobs -q '.jobs[]|select(.name|startswith("3 ·"))|"\(.conclusion//.status) id=\(.databaseId)"'
gh run rerun --job <job-id>
```

Since 2026-09-22 (decision 337) `ci.yml` triggers on `push` to `main` only, so
one commit no longer produces two runs and this should be rare — a stale run or
a re-opened PR rather than every pull request, which is what it used to be.

---

## 12. Keep branches synchronized

Before pushing a branch:

```bash
git fetch origin
git status
git log --oneline --decorate -5
```

For a personal branch:

```bash
git rebase origin/main
```

Then run tests and push:

```bash
git push --force-with-lease origin <branch-name>
```

For a shared branch, do not force-push. Merge instead:

```bash
git merge origin/main
git push origin <branch-name>
```

Never use plain `--force`:

```bash
git push --force
```

Use only:

```bash
git push --force-with-lease
```

---

## 13. Pull request rules

**Owner instruction, 2026-09-29 — never commit until the owner says so.** No `git commit` of any kind (not a "checkpoint", not "to protect finished work") unless the owner explicitly asks for a commit in the current task. Finish the work, test it, report the uncommitted changes, and wait. Protection against another session's reset comes from working in your OWN worktree, not from committing early. This supersedes the 2026-09-18 "commit without being asked" rule everywhere it appears.

~~**Commit without being asked. Never push, open a PR, merge or deploy without being asked.**
Owner instruction, 2026-09-18, answering exactly this question.~~ — **superseded 2026-09-29**
for commits; the rest of the table still stands.

| Action | Needs the owner to ask for it? | Why |
|---|---|---|
| `git add` / `git commit` on your own task branch | **Yes (since 2026-09-29)** | The owner decides when work is committed. Work in your own worktree so a reset elsewhere cannot touch it (the 2026-09-04 incident) |
| `git push` | **Yes** | It leaves this machine |
| `gh pr create`, or updating a PR | **Yes** | Outward-facing, and it asks other people for review |
| Merging a PR | **Yes** | It changes `main`, and the next deploy ships `main` |
| `sudo legalmind-deploy` | **Yes, always** | It ships to production |

"Do the work" is not "publish the work." When the task is finished, **stop and report the
branch and the uncommitted changes**, then wait to be told to commit, and separately to push. Permission to push
or merge one line of work covers that work only; it does not carry over to the next task.


Every PR must include:

- Clear title
- Short summary
- Files or components changed
- Why the change is needed
- Test commands and results
- Known limitations
- Deployment or migration notes
- Whether the change modifies specification or expected behavior

Before opening or updating a PR, check:

```bash
git status
git diff origin/main...HEAD --stat
git diff origin/main...HEAD
```

The PR branch must contain only the intended work.

Do not open multiple PRs for the same branch and task.

Do not merge a PR while:
- Required CI checks are failing
- The branch is behind and GitHub reports it must be updated
- Conflicts are unresolved
- Required reviews are missing
- A specification-change approval is missing
- A migration has not been reviewed

---

## 13a. The merge gate — run it before merging ANY pull request

**Owner instruction, 2026-09-22**, after a merge was attempted on a PR whose CI was green
and whose `mergeable` field said `MERGEABLE`, and GitHub refused it.

1. Fetch the latest `origin/main`.
2. Check the **live GitHub ruleset** and the PR state.
3. **Do not assume `mergeable: true` means the PR is allowed to merge.** That field means
   only "no content conflict". It says nothing about whether the rules permit a merge.
4. Verify every one of:
   - the PR is OPEN
   - there are no merge conflicts
   - the branch is **up to date with `main`**
   - all required status checks are successful
   - the required **Authorization matrix (RELEASE-BLOCKING)** check is successful
5. If the branch is BEHIND and the repository has strict required-status-check rules:
   update the PR branch from the latest `origin/main`, resolve any conflicts, push, **wait
   for a fresh CI run**, then re-check mergeability and branch freshness.
6. **Only then** perform a normal merge.
7. **Never use `--admin`, and never bypass a repository rule**, unless the owner
   explicitly authorizes it for that merge.
8. **Never merge on the strength of an earlier green CI run if `main` changed afterwards.**

### The trap this closes

`repos/{owner}/{repo}/branches/main/protection` returns **`404 Branch not protected`** on
this repository, and that is not the answer to "is `main` protected?". Protection here is a
**ruleset**, which that endpoint does not report. The authoritative check is:

```bash
gh api repos/{owner}/{repo}/rules/branches/main
```

which shows `strict_required_status_checks_policy: true` and the required context
`3 · Authorization matrix (RELEASE-BLOCKING)`. Reading the older endpoint and concluding
"nothing is enforced" is how a merge was attempted that the server then refused.

One more reading trap in the same output: the branch-dedupe workflow (PR #104) cancels
superseded runs, and `gh pr checks` prints every job of a **cancelled** run as `fail`. Those
are not failures. Attribute each row to its run id and check that run's `conclusion`, and
confirm the successful run's head SHA is the PR's **current** head.

Until 2026-09-22 this was every pull request's normal state, because `ci.yml` fired on
`push` for every branch as well as on `pull_request` and the `concurrency` group cancelled
one of the pair — PR #114 could not merge until that cancelled copy of the Authorization
matrix job was rerun by hand twice. `push` is now `branches: [main]` (decision 337), so a
duplicate run is the exception; §11's *"A failing check that failed nothing"* has the
one-job rerun recipe for the cases that remain.

---

## 14. Merge conflict procedure

When a conflict occurs:

```bash
git status
git diff --name-only --diff-filter=U
```

Resolve one file at a time.

Conflict markers look like:

```text
  <<<<<<< HEAD
  current branch
  =======
  incoming branch
  >>>>>>> origin/main
```

(Indented by two spaces above only so this file itself does not trip `git diff --check`.)

After resolving:

```bash
git add path/to/resolved-file
```

For a merge:

```bash
git commit
```

For a rebase:

```bash
git rebase --continue
```

Then run:

```bash
git diff --check
git status
```

If the resolution is unsafe or unclear, stop:

```bash
git merge --abort
```

or:

```bash
git rebase --abort
```

Never guess when resolving:
- Business rules
- Legal text
- Database constraints
- Security behavior
- API contracts
- Specification or lock files

Ask the owner or preserve both interpretations for review.

---

## 15. Append-only and lock files

If a file is designated append-only, do not edit or reorder existing content.

Append new records only at the end.

Before committing:

```bash
git diff -- path/to/append-only-file
```

Verify that:
- Existing lines are unchanged
- New content is appended
- No formatting tool rewrote the file
- No conflict resolution modified historical records

Never run automatic formatters on append-only specification files.

In this repository that means [all_lock.md](all_lock.md) above all — see CLAUDE.md rule 22.

---

## 16. Generated files

Do not manually edit generated files unless the repository explicitly requires it.

Find the generator:

```bash
grep -R "generate\|generated\|codegen" -n README.md Makefile pyproject.toml package.json tools scripts
```

Update the source and regenerate:

```bash
<repository generator command>
```

Then verify the generated diff is expected.

---

## 17. Database and migration safety

Before changing database schema:

- Confirm whether a migration is required
- Check for existing migrations
- Check migration ordering
- Check foreign keys and delete behavior
- Check test fixtures
- Run migration tests
- Document rollback or compatibility behavior

Never modify an already-applied migration unless explicitly authorized.

Create a new migration instead.

Do not use destructive database commands against shared or production databases.

---

## 18. Dependency changes

Do not update dependencies as part of unrelated work.

For dependency changes, include:
- Why the dependency is needed
- Version change
- Lockfile changes
- Security impact
- Test results
- Any runtime or build impact

Run the repository's dependency and security checks.

(In LegalMind a new technology, dependency or service also needs **owner approval** —
CLAUDE.md rule 19. This section is how you land one, not permission to add one.)

---

## 19. Session handoff

At the end of every session, report:

```text
Task:
Branch:
Worktree:
Commit:
Files changed:
Tests passed:
Tests skipped:
CI status:
Known problems:
Next action:
```

If work is incomplete, **ask the owner** whether to create a checkpoint commit (never on
your own, owner 2026-09-29). If they say yes:

```bash
git add <intended-files>
git commit -m "Checkpoint <task-name>"
```

Do not leave important work only in an uncommitted worktree.

---

## 20. Agent completion checklist

Before saying the task is complete:

```bash
git status
git branch --show-current
git diff --check
git diff origin/main...HEAD --stat
```

Confirm:

- [ ] Correct task branch
- [ ] Correct worktree
- [ ] No accidental `main` changes
- [ ] No unrelated files included
- [ ] No unreviewed conflict markers
- [ ] Focused tests pass
- [ ] Required full tests pass
- [ ] CI was checked
- [ ] Specification changes are documented
- [ ] Required PR labels are present
- [ ] Branch is pushed — only if the owner said push (§13)
- [ ] Worktree state is reported
- [ ] No uncommitted work is accidentally abandoned

---

## 21. Stop conditions

The agent must stop and ask for clarification when:

- The intended branch is already used by another worktree
- Uncommitted changes belong to another task
- Two agents are editing the same critical file
- A merge conflict changes business or legal meaning
- A test expectation conflicts with the written specification
- A migration appears already applied
- CI failure is unrelated to the current task
- A required secret, service, database, or dependency is unavailable
- The agent would need to discard existing work
- The agent cannot determine which version is authoritative

Never hide uncertainty by silently choosing one side of a conflict.

---

## 22. Golden rule

Before every edit, commit, rebase, merge, push, or PR update:

1. Check the current branch.
2. Check the current worktree.
3. Check the current status.
4. Check whether another session owns the files.
5. Fetch the latest remote state.
6. Make the smallest safe change.
7. Run the relevant tests.
8. Report exactly what happened.

---

# Shared working tree, worktrees and the deploy tree

*Moved verbatim from CLAUDE.md on 2026-11-09 (the restructure in `docs/00-project/AGENT_INSTRUCTIONS_AUDIT_2026-11-09.md`). The struck-through "commit as soon as verified" line is kept as history; the owner rule of 2026-09-29 (§13) governs. CLAUDE.md § Git, worktrees, deploy carries the summary.*

**Owner instruction, 2026-09-04**, after the incident below: *"Multiple development
sessions/agents may be working on this repository simultaneously… Act like a senior
engineer working on a team, not an isolated coding agent."*

Rule 23 already says completed work stays completed whoever did it. This section covers
the sharper case: another session is editing **right now**, in the same working tree.

### The 2026-09-04 incident this section responds to

Two sessions worked concurrently. Session B finished a set of simplifications, committed
**only its own four files**, then ran a `git reset` to `origin/main` — which discarded
session A's five *uncommitted* files from the working tree. Nothing warned either
session. Session A's work was unstaged, so it was **not recoverable from git**; it
survived only because a scratchpad copy of one file and the diff itself happened to still
be in that session's transcript. Session B's own commit was fine — it was on a branch.

Two lessons, both now rules: **a reset destroys everyone's uncommitted work, not just
yours**, and **work that is not committed is not safe** in a tree someone else may reset.

### The rules

- **Never `reset`, `checkout --`, `stash`, `clean` or revert files you did not modify.**
  The working tree is shared. `git reset --hard` and `git checkout -- .` are effectively
  destructive to every other session at once, and what they destroy is unrecoverable
  because it was never in the object store. If you need a clean baseline, commit your own
  work first, then reset only your own paths.
- **Never commit until the owner says so (owner, 2026-09-29).** Finished, green work stays
  uncommitted in your OWN worktree and is reported; the owner decides when it is committed.
  The worktree is the protection against another session's reset, not an early commit.
  ~~Commit your work as soon as it is verified.~~ — superseded 2026-09-29.
- **Stage by explicit path, never `git add -A` or `git add .`.** Another session's files
  are almost certainly in the tree beside yours. Name your files; check `git status` and
  the staged diff before committing; if the boundary is genuinely ambiguous, stop and
  report rather than guessing.
- **Inspect before you touch anything.** `git status`, `git branch --show-current`,
  `git log --oneline -5`, and the diff of any file you are about to edit. Unexpected
  edits in a file are a *signal*, not noise — identify their purpose and integrate with
  them.
- **A commit you did not write is not yours to land.** Before concluding a commit is
  orphaned, run `git branch --contains <sha>` — in this incident a commit was assumed
  dangling and was in fact safe on its own branch. Work sitting on another session's
  branch is that session's in-flight work heading for its own review: leave it there,
  and coordinate rather than cherry-picking it into `main`. Resurrect only work that is
  genuinely lost *and* wanted.
- **Prefer KEEP → MERGE → ADAPT → REMOVE.** "Mine is newer" is not a reason to drop
  someone else's change. If two sessions built the same thing, keep the better
  implementation — one correct implementation beats two competing ones — and never
  destroy the loser's *unrelated* work in the process.
- **Leave a coordination note** in [CHANGELOG.md](CHANGELOG.md) `[Unreleased]` or the
  relevant PR when you make a call that affects another session's work, including a
  deliberate decision *not* to integrate something and why. Agents resolve routine
  engineering conflicts between themselves; the owner is for product, legal and security
  decisions.

### Work in your own worktree — the structural fix

The rules above are mitigations. The root cause is that every session edits **one**
checkout, so one session's `reset`, `checkout`, branch switch or build churns another's
files. On 2026-09-04 that cost one session its unstaged work, put another session's
unreviewed Reviews/Report changes into a **production deploy**, and moved `HEAD` out from
under a third mid-task.

`git worktree` removes the cause: each session gets its own directory and its own `HEAD`,
sharing one object store and one set of branches. Nothing is duplicated and no history is
rewritten.

```bash
# Start of a session that will edit files:
git worktree add /root/legalmind-worktrees/<short-task-name> -b <branch> origin/main
cd /root/legalmind-worktrees/<short-task-name>
# ... work, commit, push, open the PR from here ...

# When the PR is merged:
cd /root/Legalmind.v1
git worktree remove /root/legalmind-worktrees/<short-task-name>
```

**Point a worktree at the source material, or six tests skip silently.** `legal-docs/`
is gitignored (locked 54.6) so it exists only in the deploy tree, and
`test_source_material.py` resolves it relative to *its own* root — in a fresh worktree
all six document checks skip and the run still says "passed":

```bash
export LEGALMIND_SOURCE_MATERIAL_DIR=/root/Legalmind.v1/legal-docs   # 6 skips -> 10 passed
```

A skip is not a pass. Check the skip count against the deploy tree's before believing a
green run in a worktree.

- **`/root/Legalmind.v1` is the deploy tree. Treat it as shared infrastructure, not a
  desk.** The systemd units serve straight from it, so it should sit on `main`, clean.
  Read there freely; do exploratory edits and feature work in your own worktree.
- **`git worktree list` is part of the start-of-session inspection**, alongside
  `git status` and `git branch --show-current`. It tells you who else is checked out
  where — a second worktree on a feature branch means another session is live.
- **A branch can only be checked out in one worktree at a time.** Git refuses the second
  attempt; that refusal is the feature, not an obstacle to work around.
- **Never `git worktree remove --force`** a worktree you did not create, and never one
  with uncommitted changes — that is the same destructive act as `reset`, wearing a
  different name.
- Deploying still happens from `/root/Legalmind.v1` on a clean `main`, and
  `frontend/scripts/deploy-frontend.sh` refuses a dirty tree so a deploy ships a commit
  rather than whatever someone was mid-way through.
- **The deploy tree is writable by root ONLY, as of 2026-09-16 — do not re-add group
  write.** It had 13,480 group-writable paths, `.git/config` among them. That is fine
  while only administrators deploy, and is a root escalation the moment anyone else can:
  write access to `.git/config` means `core.hooksPath`, which means the next
  `sudo legalmind-deploy` runs your script as root. Group **read** is kept, so read the
  tree freely; edit in your own worktree, which is where feature work belonged anyway.
- **`sudo legalmind-deploy` is the one root command a non-administrator may run** (owner
  decision, 2026-09-16; group `legalmind-dev`). It takes **no arguments and accepts
  none**, fast-forwards the deploy tree to `origin/main`, runs `ops/deploy.sh`, refuses a
  dirty tree, and logs the invoking account. Never widen that sudoers rule to a directory,
  a wildcard or a second command — the narrowness is the whole control. Details and the
  restore procedure: [ops/README.md](ops/README.md).
- **One deploy at a time.** `ops/deploy.sh` holds `flock -n /var/lock/legalmind-deploy.lock`
  and REFUSES rather than queues. Two overlapping deploys build the frontend into the same
  staging directory and both swap it live, so the result is a mixture of two builds and the
  rollback copy points at neither. `REFUSING: another deploy is already running` is the
  guard working — wait and re-run, never work around it.
- **Keep `main` deployable, because a deploy ships `origin/main`, not your commit.**
  Anything merged and not yet deployed goes out with the next person's unrelated change,
  and since 2026-09-16 that person may be a developer shipping a CSS fix rather than an
  administrator who knows what else is pending. Do not merge what you are not willing to
  see deployed; if you must, say so loudly and expect it to ship with the next change.

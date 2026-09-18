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

**Specification-first still governs everything.** Authorization covers **building what is already locked** and confers no authority to decide what is not. Do not implement an unspecified behavior, add a table beyond `AM-27`'s nine, or add a technology or dependency without approval. Do not invent a legal rule, threshold, or evaluator behavior. When you find a contradiction, report it — never resolve it yourself.

---

# Multi-Agent and Multi-User Development Rules

**Owner instruction, 2026-09-18 — this is the FINAL flow for every git and GitHub
operation, confirmed by the owner. There is no other procedure and no per-session
variation.** Mandatory for every coding agent, developer and automated session working in
this repository. They govern **git and GitHub operations** —
branching, worktrees, commits, pushes, PRs, conflicts, CI. They do not touch the legal
specification rules in [CLAUDE.md](CLAUDE.md), which still win on anything about what may
be built or decided.

**Where this supersedes CLAUDE.md.** [CLAUDE.md § Git workflow — one owner, keep it in
`main`](CLAUDE.md) says to commit straight to `main` and not to open a branch per task.
That is superseded by §1 below: **work on a task branch, always.** `main` is
branch-protected and rejects direct pushes anyway, and multiple agents now run
concurrently. Everything else in that section — merge promptly, delete the branch, no
retry branches, the deploy tree is `/root/Legalmind.v1` on clean `main`, one deploy at a
time — still stands.

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

Do not run these commands unless the user explicitly authorizes data loss:

```bash
git reset --hard
git clean -fd
git checkout -- .
git restore .
git stash clear
```

If you need a clean state, preserve changes first:

```bash
git stash push -u -m "preserve work before task"
```

Or create a backup branch:

```bash
git switch -c backup/<description>
git add -A
git commit -m "Checkpoint existing work"
```

Before using `git stash pop`, inspect:

```bash
git stash list
git stash show --stat stash@{0}
```

---

## 8. Commit checkpoints regularly

Make small, understandable commits.

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

If work is incomplete, create a checkpoint commit:

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
- [ ] Branch is pushed
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

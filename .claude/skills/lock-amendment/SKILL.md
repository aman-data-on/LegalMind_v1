---
name: lock-amendment
description: Append an Amendment Batch (AB-n / AM-n) or a conflict (C-n) to LegalMind's locked record — collision scan for free IDs, the append-only all_lock.md record, the LOCKED_DECISIONS.md registry, CONFLICTS.md, every affected doc/test, CHANGELOG/DAILY_CHANGED. Use whenever a change amends, extends or supersedes a locked decision, a roadmap conflict needs an amendment, or a new contradiction must be registered.
---

# Lock amendment

## 0. Is it yours to amend?

- **Owner approval exists** — an explicit yes for this change, or one of the two delegations in
  CLAUDE.md rule 6 (the Ask/RAG roadmap for roadmap conflicts; "product over locks" for product/UX
  collisions). In R&D, product-over-locks amendments are **drafted, not appended**; append when the
  owner starts the build.
- **Never covered by a delegation:** legal content or positions (rules 7/21 — the lawyer supplies
  text), authorization in every request (rule 18, `SEC-*`), the append-only audit trail, the
  zero-tolerance Legal Rule policy, the paid-model cost guard. Raise these; do not amend.
- Without approval: write the proposal per [CONTRIBUTING.md](../../../CONTRIBUTING.md) § Changing a
  locked decision (ID, verbatim current text, proposal, why, blast radius) and wait.

## 1. Collision scan — pick IDs nobody holds

Other sessions cite IDs in code before appending their record, so the tail of `all_lock.md` is
not enough (collided twice on 2026-10-26).

```bash
git fetch origin
for id in AM-NNN AB-NNN C-NN; do
  echo "== $id"
  git grep -n "\b$id\b" origin/main -- . | head -3
  for wt in $(git worktree list --porcelain | awk '/^worktree/{print $2}'); do
    grep -rIn --include='*.md' --include='*.py' --include='*.ts' --include='*.tsx' --include='*.json' \
      "\b$id\b" "$wt" 2>/dev/null | head -2
  done
  for b in $(git branch -r --format='%(refname:short)'); do
    git grep -q "\b$id\b" "$b" -- all_lock.md docs backend/legalmind 2>/dev/null && echo "taken on $b"
  done
done
```

Take a range with headroom past the highest ID seen anywhere; say in the record which range was
scanned.

## 2. Append the record

- `all_lock.md` is append-only (rule 22): add at the END only. Follow the shape of the last
  records: heading `AMENDMENT BATCH AB-n — \`AM-n\` (date): title`, the owner instruction quoted,
  then each `AM-n` with what it extends/amends/supersedes and numbered terms `r1…` in a `text`
  block.
- Never edit an earlier record, even one you are superseding — name it as superseded in the new
  record and in LOCKED_DECISIONS.md.
- Verify the prefix is byte-identical: `git diff origin/main -- all_lock.md | grep '^-' | grep -v '^---'`
  must print nothing.
- No real client, counterparty or signatory names — "the client".

## 3. Synchronise the record (one operation)

- [LOCKED_DECISIONS.md](../../../docs/00-project/LOCKED_DECISIONS.md): a row per `AM-n`; annotate
  each amended row with `⚠️ *amended by AM-n …*` (do not rewrite its text).
- [CONFLICTS.md](../../../docs/00-project/CONFLICTS.md): a table row and a full section for a new
  `C-n`; mark resolved ones with the resolving ID.
- Every affected specification doc (superseded banner, never overwrite), tests, code comments that
  cite the old behaviour.
- [IMPLEMENTATION_STATUS.md](../../../docs/00-project/IMPLEMENTATION_STATUS.md) (build state only
  if built), CHANGELOG `[Unreleased]`, and `docs/DAILY_CHANGED.md` for Ask/RAG programme changes.
- New document → [docs/README.md](../../../docs/README.md).

## 4. Check

```bash
wc -l all_lock.md                                   # report the new count
cd backend && python3 -m pytest tests/test_documentation_index.py -q
```

CI job 6 re-checks append-only; CI job 7 treats a changed corpus expectation as a spec change.

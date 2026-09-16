# Ask AI fixes — deployment runbook

📁 **OPERATIONAL. Decides nothing. Nothing here runs without owner approval.**

Prepared 2026-09-15 so that approval is the only remaining step. Covers three branches;
each is independently shippable and the order below is a dependency, not a preference.

---

## 0. What is being deployed

| Order | Branch | Contents | Gated on |
|---|---|---|---|
| 1 | `fix/language-safety-screens` | `AM-25` r4/r5 enforced in Hindi and Hinglish; grounding fails closed | `AM-69` approval |
| 2 | `fix/ask-source-leak` | Source-locator sanitizer; citation version + status | none — no lock touched |
| 3 | `feat/capability-route` | Capability route, **shipped disabled** | none to deploy; `AM-68` to *enable* |

**No database migration is required by any of the three.** The citation version and
status are joined from existing rows; the capability route adds a config file and reads
an env flag. `alembic heads` is unchanged.

---

## 1. Pre-flight

```bash
cd /root/Legalmind.v1 && git status --short          # must be clean
git worktree list                                    # who else is checked out
alembic -c backend/alembic.ini heads                 # unchanged by this work
```

Confirm the deploy tree is on `main` and clean — `frontend/scripts/deploy-frontend.sh`
refuses a dirty tree deliberately, so a deploy ships a commit rather than someone's
work in progress.

⚠️ **Do not source `/root/.legalmind.env` to run tests.** It sets `LEGALMIND_BROKER_URL`
(indexing then queues to a worker that is not running, and every retrieval test fails
with `NO_EVIDENCE_RETRIEVED`) and `LEGALMIND_GEMINI_API_KEY` (a live key in reach of any
test that does not fake generation). The correct invocation is in
[ASK_AI_PROGRAMME.md](../00-project/ASK_AI_PROGRAMME.md) §D.7.

## 2. Staging validation — already performed

Against `legalmind_v1_test`, with the Gemini key deliberately unset:

| Check | Result |
|---|---|
| `main` baseline | 57 passed, 0 failed |
| `fix/language-safety-screens` full suite | **1873 passed, 0 failed** |
| `fix/ask-source-leak` full suite | **1834 passed, 0 failed** (1 index test fixed since) |
| `feat/capability-route` capability suite | **23 passed** |
| Frontend | **474 passed**, 34 files |
| AC-12 gate, both branches | wrongly-answered **1 (held)** · recall **0.625 (held)** · retained **43 (held)** — SHIPPABLE |
| Domain A round trip | 27 passed — no locator survives into `position_chunks` |

Unmeasured, by choice: faithfulness and citation precision need real Gemini calls on the
owner's key.

## 3. Deployment steps

### 3.1 Backend (each branch, in the order above)

```bash
cd /root/Legalmind.v1
git merge --no-ff <branch>        # OWNER APPROVAL REQUIRED
systemctl restart legalmind-api   # and the worker units
```

### 3.2 ⚠️ The re-chunk — required by `fix/ask-source-leak`, and NOT optional

The sanitizer is a **write-time** fix. Until this runs, `position_chunks` keeps the
leaked text and the defect is closed in code and **open in the running system**.

```bash
cd /root/Legalmind.v1/backend
python3 -m tools.chunk_standards      # deletes and rebuilds each standard's chunks;
                                      # embed_positions runs inside it
```

This **modifies live data** and therefore needs explicit approval of its own. It is
idempotent by design (`AM-32` r3: each run deletes a standard's chunks and re-chunks the
current version), and it touches `position_chunks` / `position_chunk_embeddings` only —
no Finding, Evaluation, Review or Legal Decision is read or written.

**Verify afterwards:**

```sql
SELECT count(*) FROM assist.position_chunks
 WHERE content ILIKE '%LEGALMIND_SOURCE_MATERIAL_DIR%'
    OR content ILIKE '%docs/%' OR content ILIKE '%.md%'
    OR content ILIKE '%not named in this repository%';
-- expected: 0
```

### 3.3 Frontend

```bash
cd /root/Legalmind.v1/frontend && npm run deploy   # never a bare `next build`
```
Then confirm in a real browser, by chunk name and content — a 200 is not proof — and have
the owner reload once, since page HTML is no-cache.

### 3.4 The capability route stays OFF

Nothing to do. `LEGALMIND_CAPABILITY_ROUTE` is unset, so `routing.plan` never returns a
capability plan and no answer changes. Enabling it requires `AM-68` **and** approval of
the manifest contents.

---

## 4. Rollback

| Failure | Action | Recovers |
|---|---|---|
| Any backend regression | `git revert -m 1 <merge>`; restart | immediately |
| Position citations render wrongly | revert `c82f5ff` alone | immediately |
| Hindi routing too aggressive (a document question reaching the evaluator) | revert `d3b9985` — **reopens the guardrail bypass**, so prefer narrowing the vocabulary | immediately |
| Re-chunk produced bad chunks | re-run `tools.chunk_standards` from the previous commit | one command |
| Capability route misbehaves | unset `LEGALMIND_CAPABILITY_ROUTE` | no deploy needed |

**The re-chunk has no inverse**, and does not need one: it is a pure function of the
ratified files and the code, so any state is reproducible by checking out the desired
commit and re-running. Nothing else in the database is touched.

**Rollback risk worth stating plainly:** reverting the language-safety branch restores a
state in which a Devanagari claim passes the grounding check vacuously. Prefer a forward
fix.

---

## 5. Post-deployment checks

1. Ask "what is our liability cap?" — the citation shows code · clause · type · **version**, and **no path**.
2. Ask "हमारे मानक से तुलना करें" with a document — routes to the evaluator, not a generated answer.
3. Ask a question whose answer the document does not hold — a plain refusal, not a guess.
4. Re-run AC-12 and confirm wrongly-answered has not risen.
5. `journalctl -u legalmind-api` — no `assist.ask.capability_manifest_unavailable`.

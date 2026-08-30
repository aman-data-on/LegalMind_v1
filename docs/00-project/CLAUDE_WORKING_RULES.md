# Working rules — the operational index

**Status: ACTIVE.** Last reconciled **2026-08-25**.

> **This document restates nothing.** [CLAUDE.md](../../CLAUDE.md)'s twenty-three rules govern how
> work is done here, and [`all_lock.md`](../../all_lock.md) is the authoritative decision record.
> Where this document and either of those appear to differ, **they win and this is the defect.**
>
> That constraint is deliberate and it is the owner's: *"Never copy a locked rule and subtly change
> its meaning. Reference the authoritative document instead."* A paraphrase drifts. So every legal
> and architectural rule below is a **pointer**, and the only original content here is the
> operational protocol in §5–§8 — how to decide, when to stop, and what to do when blocked.

---

## 1. Where authority actually lives

Read in this order. Stop at the first that answers the question.

| # | Source | What it settles |
|---|---|---|
| 1 | [`all_lock.md`](../../all_lock.md) | Every locked decision, verbatim. **Append-only** — see rule 22. If this and `docs/` disagree, this wins **and you report the discrepancy** |
| 2 | [LOCKED_DECISIONS.md](LOCKED_DECISIONS.md) | The index into it, by decision ID. Search by prefix rather than reading `all_lock.md` end to end |
| 3 | [CLAUDE.md](../../CLAUDE.md) | The twenty-three working rules, the three repository traps, and the current configuration state |
| 4 | [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) | **The only document that may assert build state.** Not this one, not `LEGALMIND_PROJECT_STATE.md`, not `README.md` |
| 5 | [CONFLICTS.md](CONFLICTS.md) | Registered contradictions. Nine are open. Resolving one needs owner approval |
| 6 | [CONTRIBUTING.md](../../CONTRIBUTING.md) | The six kinds of change, and the procedure for amending a lock |
| 7 | [AUTO_MODE_DECISIONS.md](AUTO_MODE_DECISIONS.md) | Technical decisions taken autonomously — `what · why · what it does NOT decide` |

**Source hierarchy for a legal question.** Lower never overrides higher; where two sources at the
same level conflict, **stop and register it** (rule 5) rather than choosing:

```
1  Locked decisions and amendment batches            all_lock.md
2  Ratified Company Standards                        backend/config/company_standards/  (32 files)
3  The approved Legal Rule                           zero tolerance - see CLAUDE.md
4  Authoritative statute / legal source              background law ONLY; never configuration
5  Recorded product decisions                        this docs/ tree
6  Technical implementation choices                  AUTO_MODE_DECISIONS.md
7  General engineering judgement                     lowest; never beats any of the above
```

⚠️ **Level 4 is not level 2.** A statute is background law: cite it in an explanation, never load it
as configuration, and derive no Requirement, threshold or acceptance position from one. See
[CLAUDE.md](../../CLAUDE.md) § Source material.

---

## 2. The assist lane — read before touching it

Locked by **AB-3** (`AM-25`–`AM-29`, 2026-08-24) and **AB-4** (`AM-30`, `AM-31`, `IMPL-02`,
2026-08-25). All of it is in [`all_lock.md`](../../all_lock.md), indexed at
[LOCKED_DECISIONS.md](LOCKED_DECISIONS.md) §AB3 and §AB4. **Read `AM-25`'s nine terms in full before
writing any assist-lane code** — they are locked constraints, not guidance.

| Question | Where the answer is |
|---|---|
| What may the assist lane do? | `AM-25`, permitted list |
| What may it never do? | `AM-25` r1–r9, and r1/r4 in particular |
| Which model, and what may leave the building? | `AM-30` t1–t10 |
| May real contracts reach the provider? | `AM-31` g1–g5. **The gate is CLOSED** |
| Which tables may exist? | `AM-27` — nine, separate schema, *"no other table"* |
| How is it tested? | `AM-28` — Tier 2, and Tier 1 never admits it |
| What state does an answer carry? | `AM-29`, and [DECISION_STATE_MODEL.md](../02-legal-domain/DECISION_STATE_MODEL.md) § the sixth axis |
| In what order is it built? | `IMPL-02` → [IMPLEMENTATION_READINESS_GATE.md](../09-implementation/IMPLEMENTATION_READINESS_GATE.md) §5b |

### The four mistakes most available to a new session

1. **Asking the model for a verdict.** `AM-25` r1 and r4: the deterministic evaluator is the sole
   producer of every Finding, Evaluation, Classification and Rule Outcome, and *"does this document
   meet our standard?"* routes to it or is refused — never answered generatively. The evaluator is
   ~1,822 LOC and ~180 tests of working code; replacing it is the largest available unnecessary
   rewrite in this repository.
2. **Rendering a confidence score.** `AI-03` item 16 — *"The system does not use generic AI
   confidence scores"* — and rule 12. Report the `AM-29` answer state and per-citation retrieval
   scores **labelled as retrieval scores**. The product vision says "confidence"; the locked rule
   wins and the reconciliation is recorded in `DECISION_STATE_MODEL.md`.
3. **Building a gateway service.** `AM-26` keeps the modular monolith — no microservices. `AM-26`
   r1's single interface is an **in-process module boundary**.
4. **Re-deriving Domain A.** The 32 ratified Company Standards in
   [`backend/config/company_standards/`](../../backend/config/company_standards/) already **are**
   Domain A, derived from real supplied documents and clause-cited. Do not run a category-discovery
   pass; do not assume "8 categories" or a "22-conflict register" — neither exists here.

---

## 3. Legal grounding — the absolute rule

The rule itself is [CLAUDE.md](../../CLAUDE.md) rules **7** and **21**, and `AM-25` r3 for the
assist lane. Not restated here. What this section adds is the **check to run before writing a rule**:

1. Where did this come from?
2. Is it in an authoritative LegalMind source (levels 1–4 above)?
3. Can the system cite that source?
4. Is the source version identifiable?
5. Is it already represented in the configuration model?
6. Does an existing locked rule govern it?

If any answer is unknown, **do not write the rule.** Mark it:

| Marker | Meaning |
|---|---|
| `SOURCE REQUIRED` | The material does not exist in the repository. Request it from the owner. Never manufacture it |
| `DECISION REQUIRED` | The material exists but nobody has ruled. Ask, in the shape of §6 below |

Both are valid, useful states. `NOT YET SPECIFIED` is preserved, never filled in (rule 8).

**The concrete trap.** If a Company Standard defines `Match` / `Deviation` / `Missing`, those are the
available concepts. Do not invent `Preferred`, `Acceptable` or `Approval Required` because they sound
reasonable — and note that `ACCEPTABLE`/`UNACCEPTABLE`/`APPROVAL_REQUIRED` **do** exist as locked
Rule Outcome values on a *different* axis. Confusing the two axes is the specific error
[DECISION_STATE_MODEL.md](../02-legal-domain/DECISION_STATE_MODEL.md) exists to prevent.

---

## 4. Reuse before building

Rule 23 and the owner's standing instruction. Before creating **any** new module, ask *"does the
existing backend already solve this?"* — the answer is usually yes. The audited answer for the big
ones is in [EXISTING_BACKEND_REUSE_AUDIT.md](../architecture/EXISTING_BACKEND_REUSE_AUDIT.md) §16,
the **"Do Not Rebuild" list**: the schema and migrations, both evaluators, the parser, the evidence
model, the mapping engine, the `Guard` chain, the audit trail, the log redactor, the 32 standards,
the golden corpus, all tests, the `StorageBackend` Protocol, the worker infrastructure, the 39
endpoints, and the frontend design system.

Before creating a new `.md`: search for an existing document on the topic, decide whether it is
canonical, and **update it** rather than competing with it. Label status (`ACTIVE` · `LOCKED` ·
`SUPERSEDED` · `DRAFT` · `ANALYSIS`). Supersede with a banner; never overwrite and never delete
history (rule 22).

---

## 5. Decide it yourself, or ask?

**Decide yourself** when the answer follows from the architecture, the existing code, a locked rule,
established engineering practice, the tests, or a documented product requirement. Log anything
non-obvious in [AUTO_MODE_DECISIONS.md](AUTO_MODE_DECISIONS.md) in its existing format —
`what · why · what it does NOT decide`. Do not ask about naming, layering, test structure, migration
sequencing, or which of two equivalent implementations to use.

**Ask** only for: legal or business judgement · product direction · authority only the owner or the
legal team holds · an unresolved conflict between two authoritative sources · a credential · a source
document only the owner can supply.

---

## 6. How to ask

Plain language. No architecture lesson as a precondition to answering.

```
I need one decision from you: <the question, in one sentence>

Why I am asking:   one or two sentences
My recommendation: one clear option, and why
Your choices:      A. ...   B. ...   C. ...
```

Say exactly what response is needed. Do not ask four questions when one is load-bearing and three
are technical.

---

## 7. When blocked

Solve it yourself first — through an adapter, an interface, a configuration value, a mock, a feature
flag, migration sequencing, a compatibility layer, or by isolating the unresolved part behind a
boundary. **A single unavailable future dependency is not a reason to stop.**

Two constraints on that freedom:

* Do not build something irreversible on an assumption. If a wrong guess would have to be unwound,
  it is a `DECISION REQUIRED`, not a default.
* Do not build a placeholder that *looks* finished. Fake functionality that moves a phase to
  "complete" is worse than an honest gap — see §8.

---

## 8. Definition of done

A phase is complete only when implementation exists **and** tests pass **and** required security
controls exist **and** the affected documentation is updated **and** the source-of-truth rules were
respected **and** no known contradiction was silently ignored **and** the acceptance criteria are
met. Code existing is not done.

Every phase closes by updating [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) (build state),
[LEGALMIND_PROJECT_STATE.md](LEGALMIND_PROJECT_STATE.md) (the plain-language view) and
[CHANGELOG.md](../../CHANGELOG.md) — and **verifying figures before writing them**. The
"653 tests" / "No Legal Rule exists" corrections of 2026-08-25 are what happens when that step is
skipped.

---

## 9. Current phase

Phase status is **not asserted here** — that is `IMPLEMENTATION_STATUS.md`'s charter and a second
oracle is how the two drift apart. See its Build state table (unit 12 is the assist lane) and
[LEGALMIND_PROJECT_STATE.md](LEGALMIND_PROJECT_STATE.md) for the plain-language version.

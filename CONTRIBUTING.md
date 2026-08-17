# Contributing to LegalMind

How change works here. The rules themselves are in [CLAUDE.md](CLAUDE.md); this document is the procedure.

LegalMind is **specification-first**. A decision is made in the specification, then implemented — never the reverse. The cost of a quietly-changed legal rule is not a bug; it is an incorrect legal conclusion that looks authoritative.

---

## The six kinds of change

Every change is exactly one of these. Knowing which one you are making determines what you are allowed to do.

| Kind | What it is | Where it is recorded | Approval |
|---|---|---|---|
| **Locked specification** | A settled decision. Has an ID in the registry. | [`all_lock.md`](all_lock.md) + [LOCKED_DECISIONS.md](docs/00-project/LOCKED_DECISIONS.md) | **Owner approval required to change.** Never modified silently, not to fix a bug, not to make code cleaner |
| **Approved amendment** | A locked decision changed by explicit owner approval, e.g. Amendment Batch AB-1 | Appended to `all_lock.md`; registry entry updated; affected specs updated in the same operation | **Owner approval, granted in advance and recorded** |
| **Open decision** | Not decided. `NOT YET SPECIFIED`, `OD-*`, or an open `C-*` conflict | [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md), [CONFLICTS.md](docs/00-project/CONFLICTS.md) | **Do not resolve it yourself.** `NOT YET SPECIFIED` is a valid state — preserve it |
| **Implementation status** | An assertion about what is built, tested, or verified | [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) | Update as facts change. It records reality, never intent |
| **Implementation change** | Code, schema, config, infrastructure | The repository + [CHANGELOG.md](CHANGELOG.md) | Requires the behavior to be specified first. **An implementation change must never modify a locked legal or product decision** |
| **Historical / change log** | What happened and when | [CHANGELOG.md](CHANGELOG.md) (repository) · [`all_lock.md`](all_lock.md) (decisions) | Append-only in spirit |

The load-bearing rule: **an implementation change can never be the vehicle for a specification change.** If code cannot be written without departing from a locked decision, that is a signal to raise an amendment — not to depart from it.

---

## Changing a locked decision

Do not open the specification file and edit it. Instead:

1. **Name the decision explicitly** — its ID (`LIABILITY-001`, `AI-01`, `SEC-05`…), the document it lives in, and the `all_lock.md` step that locked it.
2. **Quote what it currently says.** Verbatim.
3. **State what you propose**, and precisely what changes.
4. **State why** — what breaks or cannot be represented without the change. "A better design occurred to me" is not a reason.
5. **State the blast radius** — which other locked decisions, schema tables, evaluator contracts, and golden-corpus fixtures are affected.
6. **Wait for an explicit yes.** Not silence, not a plausible inference.

On approval, the change lands as a **single synchronized operation**: `all_lock.md` (appended, never rewritten), [LOCKED_DECISIONS.md](docs/00-project/LOCKED_DECISIONS.md), [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md), [CONFLICTS.md](docs/00-project/CONFLICTS.md), and every affected specification — together, so the master record and the docs tree never diverge.

Amendment Batch AB-1 is the worked example of this process.

---

## Finding a contradiction

**Stop. Report it.** Do not pick the version you prefer, do not merge the two, do not assume the later one wins.

1. Add it to [CONFLICTS.md](docs/00-project/CONFLICTS.md) with a `C-*` ID, both sources verbatim, and a severity.
2. Say what a resolution would require.
3. Surface it to the owner.
4. Leave both sources unmodified.

If `docs/` and `all_lock.md` disagree, **`all_lock.md` wins** — and you still report the discrepancy rather than quietly following either one.

---

## Writing a specification document

* **Declare a status label at the top.** `LOCKED` · `PROVISIONAL` / `RECOMMENDED` · `UNDER REVIEW` / `IN PROGRESS` · `NOT YET SPECIFIED` · `ANALYSIS` / `PROPOSAL`. Never mix states in one document without labelling them.
* **Name the canonical basis** — which `all_lock.md` step, and which locked decision IDs it builds on.
* **Reference, do not restate.** One document owns each area (see the [documentation index](docs/README.md)); everything else links to it. Copied prose drifts and then contradicts.
* **Add worked examples in the existing style.** MATCH vs DEVIATION, `RESOLVED ≠ MATCH`, evidence traceability, configuration snapshots. They exist precisely where prose is ambiguous.
* **Never delete an example to shorten a document.** Never "clean up" example values.
* **Never invent a legal rule, threshold, tolerance, or carve-out.** A plausible invented rule is worse than a gap, because it looks authoritative.
* **Superseding, not deleting.** When a later step supersedes an earlier document, add a banner pointing to the successor and leave the earlier locked material in place.

---

## Before implementation begins

Implementation requires **explicit approval** and does not follow from the [Implementation Readiness Gate](docs/09-implementation/IMPLEMENTATION_READINESS_GATE.md) reporting readiness.

Without that approval, do not write application code, database migrations, API endpoints, frontend components, infrastructure, or CI configuration; do not install dependencies or select additional technologies; and do not generate scaffolding "to get started."

Documents under [docs/09-implementation/](docs/09-implementation/) describe a **target**. Their presence is not permission to build.

---

## Once implementation is approved

These do not relax when coding begins — see [IMPLEMENTATION_READINESS_GATE.md](docs/09-implementation/IMPLEMENTATION_READINESS_GATE.md) §6 for the standing constraints, and:

* **Behavior must be specified before it is built.** If it is not in the specification, stop and ask — do not fill the gap with a reasonable-sounding default.
* **Legal source material must be supplied, not manufactured.** Real legal documents, representative contracts, company standards and Requirement catalogues that the repository does not already contain must be **requested from the owner explicitly before you proceed**. Never invent legal content; never treat an arbitrary or illustrative example as production truth. This covers golden-corpus fixtures, configuration and seed data, threshold calibration, and any test asserting a legal conclusion. ([CLAUDE.md](CLAUDE.md) rule 21)
* **A changed golden-corpus expectation is a specification change, not a test fix.** ([Step 54](docs/08-testing/STEP_54_TESTING_STRATEGY.md))
* **Authorization tests are release-blocking.**
* **Every state value must conform to [DECISION_STATE_MODEL.md](docs/02-legal-domain/DECISION_STATE_MODEL.md).** The five axes never share a status field or enum — `AMBIGUOUS` means three different things on three different layers.
* **No new technologies, dependencies, or services** without approval; the domain boundaries in [SYSTEM_ARCHITECTURE.md](docs/05-architecture/SYSTEM_ARCHITECTURE.md) are locked.
* **Update [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md)** as work moves between specified → locked → implemented → tested → verified, and **[CHANGELOG.md](CHANGELOG.md)** for anything user- or operator-visible.

---

## Documentation hygiene

* Cross-link with **relative paths**. Keep links acyclic in intent: index → area → detail.
* Prefer small focused documents, but do not split a document just to make it smaller.
* Every document has one clear purpose and one source of truth.
* Stale or contradictory documentation gets **flagged or superseded**, never silently guessed at or quietly deleted.
* When you add a document, add it to the [documentation index](docs/README.md) in the same change.

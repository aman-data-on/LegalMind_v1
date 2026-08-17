# LegalMind V1

**Deterministic legal document analysis.** LegalMind compares a counterparty contract against the organization's approved legal standards and reports what matches, what is missing, what deviates, and what conflicts — with evidence for every claim.

**The system identifies and structures the issue. An authorized human makes the legal decision.**

```text
Finding: Limitation of Liability
Result:  Conflict
Risk:    High
Evidence: Relevant contract clause
Status:  Requires review
```

---

## Project phase

**SPECIFICATION / DESIGN. Implementation is not authorized.**

The V1 specification is complete — Steps 1–45D, 47, 49, 52–55, `REC-01`–`REC-07` and Amendment Batch AB-1 are locked. Step 45E (Golden Corpus) is in progress. The [Implementation Readiness Gate](docs/09-implementation/IMPLEMENTATION_READINESS_GATE.md) reports all nine criteria met — **it reports readiness, it does not grant it.**

Current state is authoritative in [docs/00-project/IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md), never here.

> ⚠️ A `backend/` directory containing Python source exists in the working tree and is untracked by git. It contradicts the "no implementation" state declared throughout the specification. It is recorded as **C-09** in [docs/00-project/CONFLICTS.md](docs/00-project/CONFLICTS.md) and awaits an owner decision.

---

## Start here

| | |
|---|---|
| **Where do I find X?** | [docs/README.md](docs/README.md) — the documentation index |
| What LegalMind is | [docs/00-project/PROJECT_OVERVIEW.md](docs/00-project/PROJECT_OVERVIEW.md) |
| What is settled | [docs/00-project/LOCKED_DECISIONS.md](docs/00-project/LOCKED_DECISIONS.md) |
| What is *not* settled | [docs/00-project/IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) |
| Known contradictions | [docs/00-project/CONFLICTS.md](docs/00-project/CONFLICTS.md) |
| Terminology | [docs/00-project/GLOSSARY.md](docs/00-project/GLOSSARY.md) |
| How to propose a change | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Working rules (humans and AI agents) | [CLAUDE.md](CLAUDE.md) |
| The authoritative historical record | [all_lock.md](all_lock.md) |

---

## Repository layout

```text
all_lock.md          the authoritative master specification — every decision, in order
CLAUDE.md            working rules; the twenty rules that govern all work here
AGENTS.md            pointer to CLAUDE.md for non-Claude agents
CONTRIBUTING.md      change management: what needs approval and how to ask
CHANGELOG.md         repository and specification milestones
docs/                the organized implementation reference, derived from all_lock.md
  00-project/          overview · locked decisions · status · conflicts · glossary
  01-product/          requirements · roles · workflows
  02-legal-domain/     philosophy · standards · rules · classifications · decisions
  03-document-model/   documents · versioning · evidence · processing
  04-analysis-engine/  engine · mapping · extraction · rules · explainability · evaluators
  05-architecture/     system · backend · frontend · API · database · storage
  06-security/         authentication · authorization · ownership · security model
  07-audit/            audit trail · reproducibility
  08-testing/          test strategy · golden corpus · regression
  09-implementation/   target schema · API contract · observability · deployment
```

**`all_lock.md` is authoritative.** `docs/` is the organized reference derived from it. If they disagree, `all_lock.md` wins — and the discrepancy must be **reported**, not quietly resolved.

---

## The constraints that define this system

Full text in [CLAUDE.md](CLAUDE.md); these are the ones most often violated by accident.

1. **No LLM, RAG, embeddings or vector search** in the authoritative analysis path (`AI-01`). This is locked, not a temporary simplification. Classical NLP is permitted in an assist-only role.
2. **Deterministic.** Same inputs + same configuration snapshot + same engine version → same result.
3. **The engine never makes a Legal Decision.** It produces Findings; an authorized human decides.
4. **Every Finding is explainable** as `Evidence → Fact → Standard → Rule → Result`. No generic risk score, no AI confidence percentage.
5. **Fail closed.** Insufficient evidence produces `UNABLE_TO_EVALUATE` — never a guess, never a discarded carve-out.
6. **`RESOLVED ≠ MATCH`**, and `DEVIATION` does not mean "unacceptable."
7. **Security is server-side.** Authentication → Authorization → Business Operation → Database. Knowing an object's ID is never sufficient for access.
8. **Never invent a legal requirement.** `NOT YET SPECIFIED` is a valid state — preserve it.
9. **Ask for real legal source material; never manufacture it.** If contracts, company standards, or other legal source material are needed and not in the repository, request them explicitly before proceeding. No arbitrary example becomes production truth.

---

## Development

No build, test, or run instructions exist because no implementation is authorized. When implementation is approved, the target is specified in:

* Stack — [docs/05-architecture/BACKEND_ARCHITECTURE.md](docs/05-architecture/BACKEND_ARCHITECTURE.md)
* Schema — [docs/09-implementation/DATABASE_MIGRATIONS.md](docs/09-implementation/DATABASE_MIGRATIONS.md)
* API — [docs/05-architecture/STEP_49_API_FINALIZATION.md](docs/05-architecture/STEP_49_API_FINALIZATION.md)
* Testing — [docs/08-testing/STEP_54_TESTING_STRATEGY.md](docs/08-testing/STEP_54_TESTING_STRATEGY.md)
* Deployment — [docs/09-implementation/STEP_55_DEPLOYMENT.md](docs/09-implementation/STEP_55_DEPLOYMENT.md)
* Build sequence — [docs/09-implementation/IMPLEMENTATION_READINESS_GATE.md](docs/09-implementation/IMPLEMENTATION_READINESS_GATE.md) §5

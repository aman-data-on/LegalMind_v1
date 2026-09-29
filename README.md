# LegalMind V1

**Legal document review, grounded in the company's own rulebook.** LegalMind reads a contract,
finds the clauses it actually contains, measures them against the organization's approved legal
positions, and reports what matches, what deviates, what is missing, what conflicts and what it
could not read — with the evidence for every claim.

**The system identifies and structures the issue. An authorized human makes the legal decision.**

```text
Requirement   Liability cap
Source        Constitution, Section 9 · Liability
Contract      12 months of fees paid          §6.1, page 4
Standard      12 months of FEES_PAID, aggregate
Result        Acceptable
```

There is deliberately no risk score, no confidence percentage and no "the AI thinks" — a retrieval
score is never rendered as legal confidence (rule 12, `AI-03`).

---

## How a review works, end to end

```text
upload ─► ingestion ─────► segmentation ─► mapping ──────────► applicability ─► evaluation ─► Finding
          PDF/DOCX,        clauses with     lexical terms,       confirmed ·     deterministic   + evidence
          OCR when the     their own        then grounded        declared ·      comparison,     + explanation
          text is not      numbering        semantic             expected        never a model   + Constitution
          legible                           recognition                                            citation
```

1. **Ingestion** reads PDF or DOCX, OCRs a page whose text is missing *or illegible*, and refuses a
   document whose structure never came out rather than analysing a page as if it were a clause.
2. **Segmentation** splits on the document's own clause numbering. A number is never invented — a
   fabricated section reference would corrupt every citation that follows.
3. **Mapping** matches each Requirement to clauses using configured terminology, then — where the
   words found nothing — asks the model whether a clause addresses the subject *and* states the same
   kind of position, accepting only a verbatim span (`AM-54`, `AM-60`).
4. **Applicability** decides what this document is measured against: a Requirement applies when the
   document confirms its clause (any family), when it belongs to the declared type, or when a
   Constitution sibling it names is confirmed. Everything not applied is **recorded with its
   reason** (`AM-51`, `AM-61`).
5. **Evaluation** is deterministic and model-free: two evaluators, `PRESENCE` and
   `NUMERIC_COMPARISON`, compare facts to the ratified position and fail closed.
6. **A Finding** carries its classification, its evidence, its explanation and the Constitution
   section it came from.

The reader sees three words — **Acceptable · Requires modification · Needs a decision** — derived
server-side from the engine's five determinations (`AM-56`, `AM-63`).

**The model never decides anything.** It helps *recognise* which clause addresses which requirement
and what quantity a clause states, always on a verbatim span, always recorded with the model
identity, prompt version and payload hash. The comparison, the classification and the outcome are
the deterministic evaluators' alone (`AI-01` as amended by `AM-54`).

---

## Where the legal positions come from

**The Legal Constitution is the source of truth.**
[`docs/02-legal-domain/LEGAL_CONSTITUTION_L1.10.md`](docs/02-legal-domain/LEGAL_CONSTITUTION_L1.10.md)
states the company's positions. It is **configuration source, never a runtime corpus**: it is not
chunked, indexed or retrieved. Its positions reach the engine as ratified **Company Standards** —
JSON files under [`backend/config/company_standards/`](backend/config/company_standards/), each
naming the Constitution section it restates.

Every standard declares its provenance, and the four are never mixed:

| Provenance | Meaning |
|---|---|
| **Approved through the Constitution** | Restates a clearly defined section without changing its meaning. Live. |
| **Ratified from a LeapSwitch document** | Traces to a real clause in company paper. Live. |
| **Proposed** | Drafted by the system, in `company_standards/proposed/`, read by nothing until ratified. |
| **Retired** | *"RETIRED — NOT PRESENT IN CURRENT CONSTITUTION"* — withdrawn from active review, history preserved (`AM-65`). |

A statute is **not** a Company Standard and never creates a Requirement. Statutes are background
law, cited in an explanation and reachable through Ask, never loaded as configuration.

**Which knowledge answers a question is decided deterministically, before any search.** There is no
mode selector and no model in the router. A question reaches the statute corpus when it NAMES a
source — a section, an Act, a set of Rules — or when it asks for a general rule: it carries a
jurisdiction ("under Indian law"), a rule-seeking shape ("what does the law say"), or it names who
the rule binds in the abstract ("a platform", "the injured party"). It does **not**, however much
statutory vocabulary it borrows, when it points at the reader's own paper — "this agreement", "our
standard", or simply "we". A statute citation is Act + the Act's own unit: `s. 43A`, or
`The Schedule` where the Act has no section number for it.

Where the Constitution is silent, LegalMind says so. It does not invent a position, a threshold or
a tolerance — `NOT YET SPECIFIED` is a valid, useful state.

---

## The two lanes

| | Authoritative lane | Assist lane |
|---|---|---|
| Produces | Findings, Evaluations, Classifications | Answers, citations, explanations, suggestions |
| Decides | Yes — deterministically | **Never** |
| Model use | Recognition only, on a verbatim span | Retrieval-grounded generation |
| Determinism | Same facts + same snapshot + same version → same result | No determinism claim |
| Guardrails | Fail closed, evidence required | Every sentence cited, every citation verified, refuses rather than guesses |

The assist lane is documented in
[`docs/05-architecture/ASSIST_LANE_AND_RAG.md`](docs/05-architecture/ASSIST_LANE_AND_RAG.md).

---

## Start here

| | |
|---|---|
| **What is built right now** | [docs/00-project/IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) — **the only document that may assert build state** |
| **Where we stand, in plain language** | [docs/00-project/LEGALMIND_PROJECT_STATE.md](docs/00-project/LEGALMIND_PROJECT_STATE.md) |
| **What happened yesterday, and is any of it waiting on me?** | [docs/00-project/DAILY_CHANGES.md](docs/00-project/DAILY_CHANGES.md) — the operations log: deploys, production data, credentials |
| **How the system works end to end** | [docs/00-project/ARCHITECTURE_REFERENCE.md](docs/00-project/ARCHITECTURE_REFERENCE.md) |
| **Where do I find X?** | [docs/README.md](docs/README.md) — the documentation index |
| What is settled | [docs/00-project/LOCKED_DECISIONS.md](docs/00-project/LOCKED_DECISIONS.md) |
| Known contradictions | [docs/00-project/CONFLICTS.md](docs/00-project/CONFLICTS.md) |
| Terminology | [docs/00-project/GLOSSARY.md](docs/00-project/GLOSSARY.md) |
| How to propose a change | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Working rules (humans and AI agents) | [CLAUDE.md](CLAUDE.md) |
| **Git and GitHub procedure** (branch, worktree, commit, push, PR, conflict, CI) | [AGENTS.md](AGENTS.md) § Multi-Agent and Multi-User Development Rules |
| The authoritative historical record | [all_lock.md](all_lock.md) |

**`all_lock.md` is authoritative** and append-only. `docs/` is the organized reference derived from
it. If they disagree, `all_lock.md` wins — and the discrepancy must be **reported**, not quietly
resolved. Counts and figures live in the document that owns them; this file quotes none, because a
second copy of a number that changes is a second answer.

---

## Running it

```bash
# backend
cd backend && pip install -e '.[dev]'
alembic upgrade head
python3 -m tools.import_ratified_standards        # load the ratified standards
uvicorn legalmind.api.app:app --reload

# frontend
cd frontend && npm ci && npm run dev
```

```bash
# the gates, in the order a release runs them
cd backend
python3 -m pytest tests -q                        # unit and integration
python3 -m tools.verify_terminology               # every standard reproduces its position
python3 -m tools.verify_invariants                # guarantees re-checked by another mechanism
python3 -m tools.verify_reproducibility           # historical Reviews replay identically
python3 -m tools.verify_assist_quality            # the Tier-2 answer-quality gate
python3 -m tools.calibrate_historical             # real signed paper, if any is present
cd ../frontend && npm run test:all && npm run test:e2e
```

Deployment is `bash ops/deploy.sh` — backend, then worker, then frontend, in that order for a
reason the script explains — and is documented in [ops/README.md](ops/README.md) and
[docs/09-implementation/STEP_55_DEPLOYMENT.md](docs/09-implementation/STEP_55_DEPLOYMENT.md).
`backend/` and `frontend/` carry their own READMEs for the detail.

Developers without root run `sudo legalmind-deploy` instead (owner decision, 2026-09-16): one
command, **no arguments accepted**, which fast-forwards the deploy tree to `origin/main` and runs
that same script. It refuses a dirty tree, and `ops/deploy.sh` holds a lock so a second deploy is
refused rather than interleaved. **A deploy ships `origin/main`, not your commit** — so keep `main`
to work you are willing to see live. The deploy tree itself is writable by root only; that is what
makes the grant safe, and re-adding group write would undo it.

**Backups** run nightly at 02:30 via `ops/production/backup.sh`: 14 days locally for fast
recovery, plus 90 days encrypted (GPG AES-256, applied before upload) in a private CloudPe
bucket for disaster recovery. Restore is verified into a scratch database, never assumed. See
[ops/production/README.md](ops/production/README.md#backups-and-disaster-recovery). The
off-server upload is **live since 2026-09-15** — each nightly run uploads, downloads the object
back and compares SHA-256 before reporting success, because an upload that cannot be read back is
not a backup.

---

## Legal source documents — `legal-docs/` (gitignored, never committed)

Owner-supplied documents live in [`legal-docs/`](legal-docs/README.md) inside the project (owner
ruling 2026-08-19). The directory is **gitignored**; locked 54.6 forbids these files entering
version control and `backend/tests/test_source_material.py` enforces it. Read through
`LEGALMIND_SOURCE_MATERIAL_DIR`.

It holds the company's own paper (MSA template, TOS, SLA, AUP and Privacy Policy for both brands),
two executed agreements whose counterparties are **never named in this repository**, and the Indian
statutes — background law, never a Standard or a Rule. `legal-docs/historical/` is for older signed
counterparty documents supplied for calibration: historical evidence only, never a current
position, always validated against the current Constitution.

---

## The constraints that define this system

Full text in [CLAUDE.md](CLAUDE.md); these are the ones most often broken by accident.

1. **No model decides anything in the authoritative path** (`AI-01`). Since `AM-54`/`AM-60` the
   model may help *recognise* a clause and read a quantity it states — on a verbatim span, inside
   the recorded audit trail — and nothing more. The comparison and the classification stay
   deterministic.
2. **Deterministic where it counts.** Same recognised facts + same configuration snapshot + same
   engine version → same classification, always.
3. **The engine never makes a Legal Decision.** It produces Findings; an authorized human decides.
4. **Every Finding is explainable** as `Evidence → Fact → Standard → Rule → Result`. No risk score,
   no confidence percentage.
5. **Fail closed.** Insufficient evidence produces `UNABLE_TO_EVALUATE` — never a guess, never a
   silently resolved ambiguity, never a discarded carve-out.
6. **`RESOLVED ≠ MATCH`**, and `DEVIATION` does not mean "unacceptable".
7. **Security is server-side.** Authentication → Authorization → Business Operation → Database.
   Knowing an object's ID is never sufficient; an out-of-scope object returns a byte-identical 404.
8. **Never invent a legal requirement**, a threshold, a tolerance or a basis equivalence.
9. **Ask for real legal source material; never manufacture it.** Missing material is a blocker to
   raise, not a gap to fill.

# AUTO-mode decision log — admin/standards API, 2026-08-19

**Status: 📁 RECORD.** Owner approved AUTO mode for the 5-unit plan (import tool ·
read paths · update-as-append · config audit events · tests/records) with these
rulings re-confirmed at kickoff:

* **MSA standard = 6 months / affected-service fees** (this morning's Q1 stands; the
  "12 months from C-01" line in the tasking message does not).
* **JSONB, no migration** (Q2=A stands; no `clause_standards` table, no C-13 resolution).
* **In-place editing is replaced by append-a-new-version with a mandatory reason**
  (locked rule 16); rollback = appending a version carrying the old values.

Every decision taken autonomously below is logged as: what · why · what it does NOT decide.

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 1 | Requirement **detail** returns configuration values and `created_by`; the **list** stays values-free | The detail view is the admin read path; N values × M requirements would bloat every list load | Nothing about who may hold `configuration.view` |
| 2 | Legal Rule values are returned under `configuration.view` | Both roles holding it (Legal Reviewer, Legal Admin) also hold `legal.position.view`, so LEGAL-02 is not widened | No new permission; no change to the confidential surface elsewhere |
| 3 | Audit events carry **ids, version numbers and the reason — never configuration values** | 53.3: a standard value can encode a confidential legal position; the trail must not leak what the API gates | Values remain reachable through the gated version rows the event names |
| 4 | `POST /requirements/{id}/standard` refuses an untyped replacement **at save time** | Same gate publish applies, surfaced earlier — an admin should hear about it when saving, not at publish | Publish keeps its own check (defence in depth) |
| 5 | The standard-update endpoint requires a mandatory `reason` | A standard change is a legal-position change; "why" belongs in the trail | Nothing decides what reasons are acceptable |
| 6 | Import tool marks source `RATIFIED_CONFIG` provenance (file, clause, date) — **not** `RESOLVED_CONFLICT` | The owner's C-01–C-23 register was never supplied (Q1=B); citing it would fabricate provenance | The register can be imported later under its own namespace |
| 7 | Import tool creates **draft-only** Requirements when a file carries no mapping/evaluation rules, and reports them unpublishable | 35.9 fixes no threshold; inventing mapping rules here would put a number nobody chose into every Review | The owner may supply rules later; publish stays refused until then |
| 8 | The tool never publishes; it reports what a publish would cover | Publishing is a Legal-permission, audited API action; a CLI bypassing `configuration.publish` would evade both the permission and the audit trail | — |
| 9 | Permission for the new endpoint: `configuration.draft` | It drafts a version — identical consequence to the existing version endpoint; a new permission would change the locked catalogue (27) | — |

**Verification at close: 632 passed · ruff/mypy clean · determinism byte-identical ×2 · 4× concurrent suites green · `all_lock.md` untouched (md5 7aee32af…).**


## Clause-catalogue expansion, 2026-08-19 (owner instruction: review ALL clauses)

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 10 | Positions extracted ONLY from LeapSwitch documents, clause-cited; the located conflict register used as corroboration only | Its own tracker marks C-01/04/05/07/23 "Needs owner decision" — an unresolved register cannot source a ratified position; the manager's whatever-is-stated rule makes the documents authoritative | The register's cross-document unification items stay management decisions |
| 11 | 13 Requirements now; uptime %-tiers, categorical-value comparison (governing-law VALUE), and every NDA Requirement deferred | Uptime is per-service multi-scope (modelling decision); categorical comparison needs a new evaluator type (enum change, outside IMPL-01); no LeapSwitch NDA template exists | Nothing — each is recorded in CLAUSE_CATALOGUE.md gaps |
| 12 | Presence Requirements verify the clause EXISTS; its value goes to Legal with evidence | Asserting "India is present" via keyword mapping would be value comparison smuggled through presence — a silent guess (ENG-09) | What a categorical evaluator looks like (V2) |
| 13 | `deviation_outcome` checked BEFORE threshold keys; invalid value → NOT_APPLICABLE + human | A blanket disposition and a band in one rule contradict; the blanket is the stated policy. Misconfiguration is never permission to guess | Nothing narrows: every path still reaches a human or a configured outcome |
| 14 | New standards import as draft-only (no mapping/extraction terminology invented) | 35.9 fixes no threshold; publishable only when terminology is supplied per Requirement | The terminology itself — unstarted configuration work |
| 15 | P-01 closed by the first real presence fixture; P-02/R-14 → UNSTARTED; P-05 stays blocked on an owner OPTIONAL declaration | The catalogue supersession changed their premises; statuses now match reality | Which clause, if any, is OPTIONAL |

| 16 | NDA baseline = the executed NDA, per owner designation 2026-08-19, standards scoped to the RECEIVING-party direction with the caveat recorded in every file | The owner overrode my "counterparty paper" classification with direct knowledge; the manager's whatever-is-stated rule plus the designation make it authoritative. My earlier reasoning (one-way obligations against LeapSwitch) is preserved in the changelog as the reason the caveat exists | What LeapSwitch's DISCLOSING-party NDA position is — undefined until such a document exists |

| 17 | 54.6's "never enter the repository" re-enforced as VERSION CONTROL (gitignore + zero-tracked + no-copies), replacing the outside-working-tree assertion | Owner ruling 2026-08-19 places the docs at `legal-docs/` in-project; gitignored files are untouchable by `git add -A`, and the tracked-files check catches a force-add | 54.6 itself — untouched; only my earlier stricter interpretation was owner-overridden |

**Verification at close: 647 passed · 45 corpus fixtures · ruff/mypy clean · determinism ×2 identical · `all_lock.md` untouched.**

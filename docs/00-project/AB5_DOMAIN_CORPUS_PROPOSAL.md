# AB-5 — Domain A/C corpus tables (`AM-32`): PROPOSAL

**Status: 📁 PROPOSAL — decides nothing.** Prepared 2026-08-27 for owner approval.
This is the amendment `AM-30` itself anticipated: *"Domain A / Domain C corpus tables —
No table is authorized by this record. AM-27's 'no other table' stands, and a corpus
schema requires its own amendment with a concrete design."* This document is that
concrete design.

**On approval:** the § "Text to append" below is appended verbatim to `all_lock.md`
(rule 22 — append-only), `AM-32` is added to [LOCKED_DECISIONS.md](LOCKED_DECISIONS.md),
**C-15 is closed** in [CONFLICTS.md](CONFLICTS.md), and implementation begins.
**Until then nothing is built** — no migration, no table, no code.

---

## What you are deciding, in one paragraph

Whether the assist lane may add **six new tables** (in the same separate schema `AM-27`
r1 already requires) so that "ask a question" works against **our approved positions**
(Domain A) and **statutes** (Domain C) the way it already works against uploaded
contracts (Domain B) — with each domain keeping its own tables, ingestion, provenance,
citation form and access rule, exactly per your 2026-08-25 no-flattening instruction.
Nothing about the rules engine, the five legal axes, the 30 locked tables, or the
zero-tolerance rule changes.

## Why engineering could not decide this

`AM-27` is locked: nine tables, *"no other table is authorized by this record."*
Domain A/C content satisfies neither `AM-27` r4 (a chunk derives from a Document
Version) nor the no-flattening instruction if forced into the Domain B tables.
Registered as **C-15**. Only an amendment — yours to approve — resolves it.

## Design decisions embedded in the draft (the trade-offs, honestly)

1. **No `positions` table.** The 32 ratified Company Standards already live in
   `company_standard_versions` — the locked source of truth. A copy would be the
   second-source-of-truth defect `AM-27` r4 exists to prevent. Instead
   `position_chunks` **references** the existing version row, and republishing a
   standard re-chunks it (chunks of a superseded version are deleted — the analogue of
   `AM-27` r5).
2. **Per-domain embedding tables, not one shared table.** A shared table would need a
   polymorphic foreign key; locked 42.1 requires *real* foreign keys. Three small
   identical-shaped tables are the price of referential integrity, and it is cheap.
3. **Domain A is EXTRACTIVE-ONLY — it never reaches Gemini.** `AM-30` t3 is explicit:
   *"No Company Standard value … may be included in an egressing payload."* So a
   positions answer is the ratified standard's own quoted text with its citation —
   which is also exactly what `AM-25` r3 permits the lane to state. No generation, no
   summary, no paraphrase from the provider. This is a locked consequence, not a
   choice.
4. **Domain C may use generation** (statutes are public law; no t3/t4 content), under
   the `AM-31` gate like everything else.
5. **Access is asymmetric by design.** Domain A retrieval requires `assist.ask` **and**
   `configuration.view` — an internal legal position is `LEGAL-02` material and must
   not surface to a user who cannot browse configuration. Domain C requires only
   `assist.ask`. Domain B is unchanged. Authorization stays inside the query
   (`AM-25` r6), and a permission-excluded result stays indistinguishable from an
   empty one.
6. **Citations stay real FKs.** `retrieval_runs` and `answer_citations` gain two
   nullable FK columns each (position chunk, statute chunk) with a CHECK that exactly
   one of the three chunk references is set per row. These are `AM-27`-batch tables,
   not among the 30 locked — amending their shape is within this amendment's power and
   touches no locked table.
7. **Authorizing tables does not supply statutes.** `statutes` rows require
   owner-supplied material with recorded provenance (rule 21; **C-16 stays open** and
   is unaffected by this approval). The ingestion tool refuses a statute file with no
   provenance record.

## What this amendment does NOT do

No change to: the 30 locked tables (schema invariant tests must pass unmodified —
`AM-27` r2's evidence rule applies identically here) · the five legal axes or the sixth
(`AM-29` — the same four answer states serve all three domains) · the evaluators, the
zero-tolerance rule, any Company Standard value · `AM-31` (the gate stays CLOSED) ·
rule 21 (no statute is authored or fetched by us; supplied material only) · C-16
(still open) · the golden corpus (Tier 1, untouched — `AM-28` r3).

---

## Text to append to `all_lock.md` on approval

```text
================================================================================
AMENDMENT BATCH AB-5 — Domain A and Domain C corpus tables
Approved by the owner on 2026-08-__. Proposal: docs/00-project/AB5_DOMAIN_CORPUS_PROPOSAL.md
Resolves C-15. Does not touch C-16, which remains open until statute material with
recorded provenance is supplied.
================================================================================

# `AM-32` — Domain A and Domain C corpus tables

**Amends:** `AM-27`, by permitting the tables below and no others beyond AM-27's nine.
This is the amendment AM-30's "What this record does NOT decide" anticipated.

r1   The three retrieval domains remain distinct, per the owner instruction of
     2026-08-25: separate tables, separate ingestion, separate provenance, separate
     citation semantics, separate access control. No shared content table, no
     domain-discriminator column on a content table, no flattening.

r2   AM-27 r1-r3 apply to every new table: same separate schema, the 30 locked tables
     untouched (schema invariant tests pass unmodified as the evidence), 42.1 design
     rules in full - UUID keys, UTC timestamps, REAL foreign keys, append-only where
     the data records something that happened.

r3   Domain A chunks derive from a published company_standard_versions row and
     reference it by real foreign key. There is no positions content table: the
     ratified standard remains the single source of truth. When a standard version is
     superseded, its chunks and their embeddings are hard-deleted and the new version
     is chunked (the AM-27 r5 principle, applied to configuration).

r4   Domain A output is EXTRACTIVE ONLY. AM-30 t3 forbids any Company Standard value
     in an egressing payload; therefore no Domain A retrieval result, in whole or in
     part, is ever included in a generation call. A Domain A answer is the ratified
     text quoted verbatim with its citation (standard code, version, source clause) -
     which is precisely the statement AM-25 r3 permits. No exception while t3 stands.

r5   Domain A retrieval requires assist.ask AND configuration.view, applied inside the
     query before retrieval (AM-25 r6). LEGAL-02 and SEC-07 apply: to a caller without
     configuration.view, Domain A results are indistinguishable from an empty corpus,
     and the identical AM-29 r4 refusal sentence is rendered.

r6   Domain C chunks derive from a statutes registry row. Every statutes row records:
     official title, act number and year, jurisdiction, the authoritative source
     (India Code for Indian statutes - the product vision's hard rule), source URL or
     gazette reference, version/as-amended date, the supplied file's SHA-256, and who
     supplied it and when. A statute with no provenance record cannot be ingested;
     the ingestion tool refuses it. Rule 21 stands: statute material is supplied,
     never authored, never fetched by the application.

r7   Domain C chunking is SECTION-based (section number, sub-section, marginal note
     preserved), not clause-based; a Domain C citation is Act + section, never a page
     alone. A statute is background law (CLAUDE.md source-material ruling, 2026-08-18):
     no Requirement, Company Standard, Legal Rule, threshold or acceptance position is
     derived from Domain C content, and Domain C output never enters the evaluator.

r8   Domain C content is public law and MAY be included in generation payloads,
     subject to the AM-31 gate and every AM-30 term. Domain A content may not (r4).

PERMITTED TABLES (six, in the AM-27 schema; no other table)
  position_chunks               derived text spans of a published Company Standard
                                version, with source-clause citation fields
  position_chunk_embeddings     one row per position chunk per embedding model
  statutes                      the statute registry: identity + provenance (r6)
  statute_chunks                section-based text spans of a statute (r7)
  statute_chunk_embeddings      one row per statute chunk per embedding model
  (sixth slot reserved)         judgments registry - NOT authorized here; a further
                                record names it when the curated list is supplied

MODIFIED AM-27 TABLES (two, both AM-27-batch tables; no locked table is touched)
  retrieval_runs                gains nullable position_chunk / statute_chunk FK
                                references alongside the existing chunk references
  answer_citations              gains nullable position_chunk_id and statute_chunk_id,
                                with a CHECK that exactly one chunk reference is set

r9   The embedding model, the calibrated refusal gate, the guardrails, the sixth-axis
     answer states and the refusal sentence are shared machinery across domains; the
     Tier 2 evaluation set gains Domain A and Domain C questions, including
     unanswerable ones, before either domain ships (AM-28's gate applies per domain).

r10  audit_events gains new event types for Domain A/C ingestion and retrieval, and
     no schema change. No statute text or standard text enters a log line (53.3).
```

---

## What implementation will look like (so approval is informed — not part of the lock)

One migration (new tables only, invariant tests untouched) · `tools/chunk_standards.py`
(re-runs on publish) · statute intake tool with mandatory provenance prompt · retrieval
extended with two more SQL branches under the same calibrated gate · workspace panes
switch from placeholder to live · Tier 2 evaluation set extended before ship (r9).
Estimate: 2–3 sessions once approved, statutes excepted (C-16).

## The one-line approval

Reply **"AM-32 approved"** (optionally with changes) and I will append the record,
update the registry, close C-15, and begin implementation in the locked order.

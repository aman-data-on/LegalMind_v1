# Step 55 — Deployment / Infrastructure

**Status: 🔒 LOCKED (2026-08-17).** No locked decision changed. Schema impact: none.

Prepared 2026-08-17. Builds on locked Step 39 (stack + security checklist), Steps 26/29/41.26 (immutability), Step 47 and Step 53.

---

# 55.1 Deployment shape

Step 39's recommended V1 shape is kept deliberately simple. No new technology is introduced (locked rule 19).

```text
Browser → Next.js (frontend) → FastAPI (API + services)
                                  ├── PostgreSQL      system of record
                                  ├── Object storage  original documents
                                  └── Worker + queue  document processing, analysis
                               → OIDC provider (external, Step 47)
```

Workers run the same application image as the API; a Review's analysis is a job, not a separate service. **No microservice decomposition in V1** (locked 38.26).

---

# 55.2 Security configuration — from Step 39's checklist

| Control | Requirement |
|---|---|
| TLS | Everywhere, including between the app and the database where the network is not fully trusted |
| Secrets | Outside source control; injected at runtime; rotatable without a code change (S-6) |
| Session/OIDC config | Client id/secret, issuer, JWKS endpoint as environment configuration |
| Encrypted storage | Documents encrypted at rest where the platform supports it |
| Upload validation | Type, size and structure validated before parsing |
| Safe parsing | Document parsing sandboxed and resource-limited; a malformed file must not compromise the host |
| Malware scanning | Where available, before a document is processed |
| Rate limiting | At the edge (reverse proxy) **and** in the application for authentication and analysis endpoints (S-5) |
| Backups | Automated, restore-tested. **Restore is verified, not assumed** |
| Database roles | The application role holds no DDL rights; migrations run under a separate role |

---

# 55.3 Environments

```text
Development   synthetic data only
Staging       production-shaped; no real counterparty contracts
Production    real legal documents
```

Real contracts never leave production. Debugging uses correlation identifiers (49.9) and diagnostics (53.1), not data copies.

---

# 55.4 Migration discipline

Locked immutability makes migrations unusually constrained:

1. **Historical legal records are never rewritten.** Audit events, superseded decisions, evaluations and document versions are append-only or immutable (AUD-01, 41.26, Step 26).
2. Migrations are **forward-only and additive** where they touch legal data. A destructive migration against `findings`, `evaluations`, `legal_decisions`, `audit_events` or `document_versions` requires explicit approval.
3. **Reproducibility must survive migration.** After any migration, historical Reviews must still replay identically (ENG-11) — this is a release-gate test (54.3), not an assumption.
4. Deferred constraint triggers (EV-MIN) must be created with their tables; a backfill cannot bypass them.
5. Configuration versions are never mutated in place — new versions only (Step 29).

---

# 55.5 Release process

```text
Golden corpus passes (54.7)
   ↓
Authorization + invariant + determinism tests pass
   ↓
Migration applied forward-only
   ↓
Post-migration reproducibility check
   ↓
Deploy API + workers together (same image)
   ↓
Verify: OIDC login, session revocation, one analysis end-to-end
```

API and workers deploy together because they share the evaluator; a version skew between them would break `evaluator_version` reproducibility.

---

# 55.6 Production blockers

Adapted from the external reference's most transferable practice — an explicit register rather than an implicit assumption.

| Blocker | Status |
|---|---|
| OIDC provider configured and reachable | Deployment prerequisite |
| Secrets management in place | Deployment prerequisite |
| Backup **and verified restore** | Deployment prerequisite |
| Rate limiting active | Deployment prerequisite |
| TLS terminated correctly, secure cookie flags set | Deployment prerequisite |
| Malware scanning available or explicitly accepted as absent | Decision required at deployment |
| Retention policy defined (locked 41.26 defers it) | **NOT YET SPECIFIED** |
| Export formats (locked as NOT YET SPECIFIED) | Blocks export feature only |

**NOT YET SPECIFIED:** hosting platform, container orchestration, CI/CD tooling, object-storage provider, monitoring stack, disaster-recovery objectives. None is determined by a locked decision; each is an operational choice at deployment time.

> ⚠️ **`CI/CD tooling` in the line above is SUPERSEDED — `REC-08`, 🔒 2026-08-17.**
>
> The original text is retained exactly as locked and is **not** rewritten. One line item of its list no longer holds: **CI/CD tooling is GitHub Actions**, by explicit owner decision. The Step 39 stack table's `CI/CD` row was the intended tooling decision and governs; this resolved conflict **C-11**.
>
> **Every other item in the list above stands unchanged** and remains NOT YET SPECIFIED — hosting platform, container orchestration, object-storage provider, monitoring stack, disaster-recovery objectives. `REC-08` is deliberately narrow and confers no authority over any of them.
>
> Lock record: [`all_lock.md`](../../all_lock.md) under "Reconciliation Decision REC-08 — CI/CD tooling" · Registry: [LOCKED_DECISIONS.md](../00-project/LOCKED_DECISIONS.md) §R · Conflict: [CONFLICTS.md](../00-project/CONFLICTS.md) C-11

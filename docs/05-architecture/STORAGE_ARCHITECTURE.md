# Storage Architecture

Canonical source: `all_lock.md` (Step 38.6 Document Storage, Step 39 "Storage", Step 34 original-file preservation)

**Status: LOCKED** for the storage *responsibilities and immutability rules* (Steps 34, 38).
**Status: RECOMMENDED (not yet locked)** for the specific storage technology narrative in Step 39, except that the Step 39 locked stack table names object storage as part of the stack — see [BACKEND_ARCHITECTURE.md](BACKEND_ARCHITECTURE.md) for the full locked stack listing.

---

## Division of responsibility (Step 39)

Use:

```text
PostgreSQL
+
S3-compatible object storage
```

Database:

```text
metadata
relationships
rules
findings
audit
```

Object storage:

```text
original.pdf
original.docx
OCR output
derived artifacts
```

Never put a 20 MB PDF directly into a normal PostgreSQL row unless there is a very specific reason.

---

## Original file preservation

**Status: LOCKED** (Step 2, Step 34)

The original uploaded file must remain unchanged. Any customized contract is a separate version/document. Derived artifacts (OCR output, extracted text, normalized text) never replace the original — they are stored alongside it.

Canonical detail: [PROCESSING_PIPELINE.md](../03-document-model/PROCESSING_PIPELINE.md) and [DOCUMENT_VERSIONING.md](../03-document-model/DOCUMENT_VERSIONING.md).

---

## Document Storage domain (Step 38.6)

The Document Storage domain is one of the locked architectural domains. See [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) §38.6 for the canonical domain description; it is not duplicated here.

The database column that references stored objects (`storage_key`) is defined in [DATABASE_MIGRATIONS.md](../09-implementation/DATABASE_MIGRATIONS.md).

---

## NOT YET SPECIFIED

* Specific object-storage provider/bucket layout
* Retention, lifecycle, and archival policy
* Encryption-at-rest key management
* Backup/restore runbook (Step 39 lists "Database backups" as a recommended control only)

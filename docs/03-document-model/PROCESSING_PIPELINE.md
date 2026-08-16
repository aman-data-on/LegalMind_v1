# Document Ingestion & Parsing Pipeline

Source: Step 34 (all_lock.md lines 3592–3999, 4553–4579). Canonical source: all_lock.md (Steps 33-35).

> Status: LOCKED — the author's closing decision for this step is explicit: "🔒 **STEP 34 — LOCKED**" (see [Final review — Step 34](#final-review--step-34) below).

This defines how LegalMind gets a reliable, versioned representation of the contract before any legal analysis happens.

(Note: the author states Step 34 and Step 35 would be handled together but locked separately, "because they define two different technical/legal boundaries.")

## 34.1 Core principle

LegalMind must **never analyze the raw uploaded file directly as if extraction were guaranteed**.

The pipeline should be:

```text
Uploaded File
     ↓
File Validation
     ↓
Document Fingerprint
     ↓
Document Version
     ↓
Text / Structure Extraction
     ↓
Extraction Validation
     ↓
Normalized Document Representation
     ↓
Analysis Engine
```

The original uploaded file must remain preserved.

## 34.2 V1 supported formats

### Primary V1

```text
PDF
DOCX
```

These cover the majority of business contracts.

### Not primary V1

```text
XLSX
PPTX
Images
Email files
Scanned handwritten documents
```

They can be evaluated later.

## 34.3 Scanned PDFs

There are two kinds of PDFs:

### Text PDF

```text
PDF
 ↓
Text extraction
 ↓
Good
```

### Scanned PDF

```text
PDF
 ↓
No usable text
 ↓
OCR
 ↓
Text
```

LegalMind should detect when normal extraction is insufficient and use OCR where supported. But OCR output must be marked as OCR-derived.

Example:

```text
Evidence Source:
OCR

Extraction Confidence:
LOW / MEDIUM / HIGH
```

We should **never silently treat OCR output as equivalent to clean native text**.

See [EVIDENCE_MODEL.md](./EVIDENCE_MODEL.md) for how OCR-derived evidence is treated as an evidence-quality concept.

## 34.4 OCR failure

Suppose the document is:

* blurry
* handwritten
* rotated badly
* extremely low quality
* password protected
* corrupted

LegalMind should not invent missing text. Instead:

```text
EXTRACTION_FAILED
```

or, if only part of the document is affected:

```text
PARTIAL_EXTRACTION
```

Then the affected Finding can become:

```text
UNABLE_TO_EVALUATE
```

rather than making a false legal conclusion.

## 34.5 Preserve the original file

For every uploaded document:

```text
Original File
     ↓
Immutable Storage
```

Never modify the original file during processing. Create derived artifacts separately:

```text
Original PDF
   ↓
Extracted Text
   ↓
Normalized Structure
   ↓
Evidence
```

This is important for auditability.

## 34.6 Document fingerprint

Every uploaded file should receive a cryptographic fingerprint.

Example:

```text
SHA-256
```

Conceptually:

```text
File
 ↓
SHA-256
 ↓
abcdef123...
```

This lets us detect exact duplicates. If the exact same file is uploaded again:

```text
Same fingerprint
```

LegalMind should not blindly create another contractual version.

See [DOCUMENT_VERSIONING.md § 33.4](./DOCUMENT_VERSIONING.md#334-how-does-legalmind-know-its-a-new-version) for how this fingerprint feeds into version-detection logic, and [EVIDENCE_MODEL.md](./EVIDENCE_MODEL.md) for the fingerprint as an evidence-anchoring concept.

## 34.7 Document structure

We shouldn't store only one giant text blob. The normalized representation should preserve structure such as:

```text
Document
 ├── Page
 ├── Section
 ├── Heading
 ├── Paragraph
 ├── Clause
 ├── Table
 └── List
```

For example:

```text
Section 8
  ↓
8.1
8.2 Limitation of Liability
8.3 Indemnification
```

This directly supports Step 32 Evidence.

## 34.8 Clause numbering

The parser should preserve existing numbering.

Example:

```text
8.2
8.2.1
(a)
(b)
(i)
(ii)
```

We should not depend solely on automatically generated numbering. The original numbering is part of the contract's structure.

## 34.9 Tables

Contracts often contain important legal information in tables.

Example:

| Service  | Liability | Term      |
| -------- | --------- | --------- |
| Standard | 6 months  | 12 months |
| Premium  | 12 months | 24 months |

The parser must preserve table content in a structured representation rather than dropping it. Otherwise LegalMind could miss legally relevant provisions.

## 34.10 Headers and footers

Headers and footers should be identified separately.

For example:

```text
CONFIDENTIAL
ABC Corp MSA
Page 7 of 24
```

should not accidentally become part of the liability clause. However, the original positional information should remain available where needed.

## 34.11 Page references

Each extracted element should retain its source page where possible.

Example:

```text
Clause:
8.2

Page:
7

Text:
"...previous twelve months..."
```

This allows the UI to jump back to the original document location.

## 34.12 Normalization

We can normalize things like:

```text
multiple spaces
line breaks
hyphenation caused by PDF layout
encoding problems
```

But we must preserve the **original extracted source text** as evidence. So:

```text
Original Source Text
        +
Normalized Text
```

not:

```text
Original discarded
```

## 34.13 Document extraction status

Controlled statuses:

```text
UPLOADED
PROCESSING
EXTRACTED
PARTIALLY_EXTRACTED
EXTRACTION_FAILED
```

This is separate from the Review lifecycle from Step 30.

For example:

```text
Review:
PROCESSING

Document:
PARTIALLY_EXTRACTED
```

The Review should not proceed to normal deterministic analysis if required evidence cannot be reliably extracted.

## 34.14 Document ingestion security

The ingestion layer must treat uploaded documents as untrusted input.

At minimum:

```text
File type validation
File size limits
Malware/security scanning where available
Safe parsing
No execution of document macros/scripts
Isolated processing
Access control
```

DOCX files must not be treated as executable content.

## 34.15 Step 34 recommended locked rules

1. V1 primarily supports PDF and DOCX.
2. Original uploaded files are preserved immutably.
3. Document Versions are immutable once used by a Review.
4. Every file receives a cryptographic fingerprint/hash.
5. Exact duplicate files should be detectable.
6. Native PDF/DOCX text extraction is preferred.
7. OCR is used when a supported PDF does not contain usable text.
8. OCR-derived content is explicitly identified.
9. Extraction failures never result in invented text or legal conclusions.
10. Partial extraction is explicitly represented.
11. The normalized document representation preserves pages, sections, clauses, paragraphs, lists, and tables where technically available.
12. Existing clause numbering is preserved.
13. Relevant source locations are retained for Evidence.
14. Original extracted text is preserved alongside normalized text.
15. Document extraction status is separate from Review lifecycle status.
16. Uploaded files are treated as untrusted input and processed safely.
17. Documents with insufficient reliable extraction may produce `UNABLE_TO_EVALUATE` rather than a fabricated Finding.
18. The ingestion layer must not alter the original source document.

## Final review — Step 34

The author rechecked Step 34 specifically for:

* Original document preservation
* Immutable document versions
* PDF/DOCX handling
* OCR vs native text
* Extraction failure handling
* Tables and clause structure
* Section/clause numbering
* Page-level evidence
* Normalized vs original text
* Duplicate detection
* Security of uploaded documents
* Extraction status vs Review status
* `UNABLE_TO_EVALUATE` instead of guessing

**Clarification added to the design:** OCR is an **extraction mechanism**, not a legal-analysis mechanism. OCR output must remain identifiable as OCR-derived evidence.

### Decision

🔒 **STEP 34 — LOCKED**

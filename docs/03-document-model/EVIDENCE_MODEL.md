# Evidence Model

Source: Step 33 (33.4), Step 34 (34.3, 34.5, 34.6, 34.7, 34.10, 34.11, 34.12), Step 35 (35.16) — all_lock.md lines 2975–4666. Canonical source: all_lock.md (Steps 33-35).

This file collects the evidence-as-a-concept pieces that are scattered across Steps 33–35, so the idea of "evidence" has one dedicated home. It does not duplicate the full pipeline or mapping mechanics — see [PROCESSING_PIPELINE.md](./PROCESSING_PIPELINE.md) and [../04-analysis-engine/REQUIREMENT_MAPPING.md](../04-analysis-engine/REQUIREMENT_MAPPING.md) for those.

> Status: the underlying steps carry mixed lock status. Step 34 material below is LOCKED (see PROCESSING_PIPELINE.md). Step 35 mapping-evidence material below is LOCKED (see REQUIREMENT_MAPPING.md). The Step 33 fingerprint-for-versioning material is PROVISIONAL (see DOCUMENT_VERSIONING.md).

## Document fingerprint as evidence anchor

Every uploaded file should receive a cryptographic fingerprint (Step 34.6):

```text
File
 ↓
SHA-256
 ↓
abcdef123...
```

This lets LegalMind detect exact duplicates. If the exact same file is uploaded again:

```text
Same fingerprint
```

the system should not blindly create another contractual version.

The same fingerprinting concept appears in Step 33.4 as the mechanism for detecting whether a newly uploaded document is a candidate new version:

```text
PDF
 ↓
SHA-256
 ↓
Document Fingerprint
```

Important caveat carried over from Step 33.4:

> A different file does not automatically mean a legally meaningful version change.

Metadata or formatting could change while the substantive contract remains the same. The fingerprint is a detection signal, not a legal determination — see [DOCUMENT_VERSIONING.md § 33.4](./DOCUMENT_VERSIONING.md#334-how-does-legalmind-know-its-a-new-version) for the versioning consequences of this.

## Original file preservation as evidence integrity

For every uploaded document (Step 34.5):

```text
Original File
     ↓
Immutable Storage
```

Never modify the original file during processing. Derived artifacts are created separately:

```text
Original PDF
   ↓
Extracted Text
   ↓
Normalized Structure
   ↓
Evidence
```

This is important for auditability — the chain from original file to normalized structure to "Evidence" is explicit in the source.

## OCR-derived content as a distinct evidence class

From Step 34.3: LegalMind should detect when normal extraction is insufficient and use OCR where supported, but OCR output must be marked as OCR-derived:

```text
Evidence Source:
OCR

Extraction Confidence:
LOW / MEDIUM / HIGH
```

We should **never silently treat OCR output as equivalent to clean native text.** The final review for Step 34 reinforces this as a clarification added to the design: OCR is an **extraction mechanism**, not a legal-analysis mechanism, and OCR output must remain identifiable as OCR-derived evidence. Full extraction-failure handling (`EXTRACTION_FAILED`, `PARTIAL_EXTRACTION`, `UNABLE_TO_EVALUATE`) lives in [PROCESSING_PIPELINE.md § 34.4](./PROCESSING_PIPELINE.md#344-ocr-failure).

## Structural evidence: sections, clauses, tables, page references

From Step 34.7, the normalized representation preserves structure (page, section, heading, paragraph, clause, table, list) rather than one giant text blob — this directly supports evidence retrieval.

From Step 34.11, each extracted element retains its source page where possible:

```text
Clause:
8.2

Page:
7

Text:
"...previous twelve months..."
```

This allows the UI to jump back to the original document location — i.e., every piece of evidence is traceable to a specific page/clause.

From Step 34.10, headers/footers are identified separately so boilerplate (e.g. `CONFIDENTIAL`, page numbers) does not get treated as evidence within a substantive clause, while original positional information remains available where needed.

From Step 34.12, normalization (spacing, line breaks, hyphenation, encoding fixes) must not discard the original extracted source text — both are retained:

```text
Original Source Text
        +
Normalized Text
```

The original extracted text is itself part of the evidence trail, distinct from the normalized/display text.

## Mapping evidence (Step 35.16)

Every clause-to-Requirement mapping should retain its reason, forming the evidence for *why* a mapping was made:

```text
Requirement:
LIABILITY-001

Mapped Clause:
8.2

Why:
- Section heading matched
- Alias matched
- Required keyword group matched
- No exclusion pattern detected
```

This becomes part of the Step 32 explainability chain. See [../04-analysis-engine/REQUIREMENT_MAPPING.md § 35.16](../04-analysis-engine/REQUIREMENT_MAPPING.md#3516-mapping-evidence) for the full mapping-engine context this evidence is generated within, and § 35.8 for the deterministic scoring evidence (matched phrases, section, candidate score) that accompanies it.

## Summary: what counts as "evidence" in this range

Across Steps 33–35, "evidence" consistently means: a traceable, non-fabricated link back to a specific source location or deterministic reason —

* a document fingerprint/hash anchoring identity,
* the preserved original file and original extracted text,
* page/clause/section location of extracted text,
* explicit OCR-vs-native provenance and confidence,
* explicit extraction status rather than invented text, and
* an explicit, itemized reason for every confirmed requirement mapping.

None of this is itself a legal conclusion — evidence supports Findings and Legal Decisions but does not constitute them (this separation is stated explicitly for version diffs in [DOCUMENT_VERSIONING.md § 33.16](./DOCUMENT_VERSIONING.md#3316-but-dont-make-version-diff-equal-to-legal-conclusion) and for mapping vs evaluation in [REQUIREMENT_MAPPING.md § 35.13](../04-analysis-engine/REQUIREMENT_MAPPING.md#3513-multiple-clauses-can-map-to-one-requirement)).

# Document reading — status

**Status: ✅ DEPLOYED 2026-10-16 12:58 IST as `01d4291` (PR #205). Docling is OFF until provisioned
(§6).** Built in the worktree `/root/legalmind-worktrees/document-reading-20261015`, removed after merge.
Owner instruction 2026-10-15 ("make legal-document ingestion reliable enough that LegalMind
does not miss or misinterpret material clauses, tables, exceptions or annexures").

The hand-over for the audit: what was wrong, what was fixed, what was measured, how to run it,
what is left, and which locks it touches (`AM-144`, AB-89). It decides nothing beyond `AM-144`.

Owner decisions taken during the work (2026-10-15): **"use docling"**; **"legal contract hindi
mein nahi hota"** — contracts are English, OCR is `eng` only.

---

## 1. What was wrong (verified, with reproductions)

Every claim was reproduced against the code by six read-only verifiers before anything changed;
a completeness critic and two later reviews added more. The defects that mattered:

| Area | Defect | Effect |
|---|---|---|
| PDF tables | No table detection: cells came out one per line inside the clause | SLA credit tiers lost their rows (`15%` beside nothing); the 2026-09 attempt was withdrawn (26014d8) because it moved tables out of their clause and cost retrieval |
| PDF clause numbers | A zero-width space after the number (`6.1.​`) | `MSA-Feb.pdf`: 1 of 47 segments numbered; now 195 of 230 |
| PDF scans | A sideways or upside-down scan was OCR'd to gibberish and stored **COMPLETE** | Garbage evidence; no orientation detection, no OCR quality check |
| PDF mixed pages | An image with text on a page that also has a text layer was never read | A scanned annexure pasted onto a typed page vanished; page still COMPLETE |
| PDF rotation | The column sort used the rotated page height; an image region on a rotated page was clipped in the wrong coordinates | Reversed clauses on a 270° page; a rotated annex lost silently |
| OCR | English only, no language, no confidence, pages OCR'd one at a time | Fail-open on bad scans; 3.5× slower than needed |
| DOCX tables | Tab-joined cells collapsed by normalisation; merged cells repeated; nested tables dropped; tables placed after all body text with no page | Rows unreadable; a table filed under the last annexure |
| DOCX pages | Breaks inside table cells not counted | Every page after a page-spanning table one low |
| DOCX stories | Headers, footers, footnotes, endnotes, text boxes, custom XML, rows in content controls never read; **hidden text read**; comments silent | Fee qualifiers in footnotes missing; invisible text in evidence |
| Ask readiness | A version with no chunks (processing, unreadable, refused index) was "read whole" with the gate **open** and zero records | Ask answered "the document does not state X" about a document it never read |
| Ask provenance | Page dropped whenever a clause number existed; OCR/table origin never reached the model or the Sources | No "read by OCR" anywhere in Ask |
| Ordering | Index sorted page-less rows first; four readers sorted by a random uuid tie-break, two of them across runs | Non-deterministic type suggestion / obligations input |
| Chat files | One scanned page failed the whole file (`OCR_REQUIRED`), every text page lost | |

Full evidence: the verify, review and critic files under the session scratchpad (not in the
repository, locked 54.6).

## 2. What was fixed

**PDF (`ingestion/parsing.py`).** Ruled tables are read with PyMuPDF `find_tables
(strategy="lines_strict")` behind a ruled-line gate and kept **in place inside their clause** as
`| a | b |` rows (`table_row`, the one serializer for PDF and DOCX); a table replaces its lines
only when the words and non-space characters are identical and the lines are consecutive, and a
table header line is never cut into its own heading. Zero-width spaces are read as spaces by
clause detection only (content untouched, 34.12). The column sort uses the cropbox and is skipped
on mostly-vertical pages. OCR runs `tesseract -l <LEGALMIND_OCR_LANGS, default eng> --psm 1 txt
tsv` (orientation detection + mean word confidence), every page needing OCR in one parallel pass;
a page under 60 mean confidence **fails closed**, under 80 is kept and listed
(`pages_low_confidence`); a document-level legibility backstop judges only the OCR a page score
cannot vouch for. Images covering ≥15% of a page with no text layer over them are OCR'd as
regions (clip in rotated coordinates); a region that cannot be read makes the page **PARTIAL**.
`ocr=False` reads the text layer only, for callers that cannot wait.

**Docling (owner: "use docling").** Docling 2.139.0 reads **tables only**, from its own venv
(`ops/docling/requirements.txt`), as an offline child process (`docling_runner.py`), one at a
time, in runs of at most 12 pages, first in line for the OOM killer (`choom -n 1000`), on pages
with ≥3 thin horizontal rules of one width. Its tables pass the same character check **and** a
cell-position check (every cell's text must be the page's own words inside that cell's box), so it
can only regroup a page's words into rows — never add, drop, move or rewrite prose. Any failure
falls back to the standard reading. **Off unless** `LEGALMIND_DOCLING_PYTHON` and
`LEGALMIND_DOCLING_MODELS` are set; with them set, an upload with a table page is read in the
background run. Never used for DOCX, text, or chat files.

Why tables only: as a prose reader (first build) Docling duplicated a paragraph across a page
break, moved a notice address from clause 20.2 to 20.3, and could drop "not" / "except" within its
word budget — found by the adversarial review on the approved corpus. As a table reader it adds
SLA-cloudpe's horizontal-rule credit tables (5/10/20%), which PyMuPDF cannot read.

**DOCX (`ingestion/parsing.py`).** Read in body order: tables where they stand with the page of
their first cell, cells once (gridSpan), vMerge values on every row, nested tables inline
`[a | b; c | d]`, text boxes after their anchor (DrawingML fallback copy skipped), footnotes and
endnotes right after the paragraph that references them, headers/footers once at the end as
`OTHER` with `part` metadata (never a clause: `mapping.body_rows`, Diff-Talk, version comparison,
unmatched provisions all skip them). Hidden, deleted and moved-from text is never read — nor a
note or text box anchored in it. A row split across a page counts as one boundary. A damaged
auxiliary part or imported/embedded content is a diagnostic and makes the reading **PARTIAL**.

**Ask (`assist/agent/tools.py`, `agent.py`, `agent_verify.py`, `service.py`, `retrieval.py`).**
One `document_gap` decides whether the selected version's text is missing or incomplete
(processing · unreadable · not_indexed · index_refused · partial · low_ocr). With no text the
documents gate stays **shut**, the model's "the document does not state X" is dropped, and a
**code-written** note (en / Hinglish / Hindi) opens the reply; partial and low-OCR readings are
read as before with the note closing the reply and one sentence in the model's header. Such turns
are neither cached nor replayed. Records carry `page` and `read_by` (OCR/TABLE) to the model and
to the Sources list, live and on replay; pinned evidence keeps its location. Index refusals are
kept on the run (`assist_index_refused`), cleared by a later index that passes.

**Chat files (`api/routers/assist.py`, `assist/agent/attachments.py`).** A file with scanned
pages is OCR'd inline up to 20 pages within 240 s; above that its text pages are kept and the
scanned ones reported unread (`pages_unread`, shown to the model and in the chat). Duplicate bytes
and the file limit are settled before any parse; uploads share the Ask rate limit. Only a
COMPLETE parse is reviewed (`AM-143` r5); the newest file is never replaced by an older one.

**Readers.** Index, version groups, type suggestion, obligations, explanations and the report
order by page, offset, id with NULLS LAST and read the latest run only. Long tables split at row
boundaries (`clause-aware-6`). An annexure label with content on its first line is recognised.

**API / UI.** `GET /document-versions/{id}` returns `pages_failed`, `pages_to_check` (never the
word "confidence", rule 12) and `assist_index.refused`. The document footer says when a document
was read in part; Sources show "page N" and "read by OCR"; chat files show unread pages.

`PROCESSOR_VERSION` → `legalmind-ingest-v5`, `CHUNKING_ALGORITHM_VERSION` → `clause-aware-6`.
Existing evidence is never re-parsed (rule 17); a re-upload or reprocess reads with v5.

## 3. Measurements

**Parser, 24 approved / derived documents**, references transcribed from rendered page images and
adversarially re-checked (zero Gemini):

| | Old parser | Fixed (Docling off) | Docling, whole pages |
|---|---|---|---|
| Passages read | 91.5% | **94.2%** | 95.6% |
| Table cells correct | 3.7% | **27.2%** (native PDF 0 → 46.5%) | 89.2% |
| Table rows kept | 2.5% | **24.7%** | 81.1% |
| Reading order | 89.3% | **92.1%** | 89.6% |
| Mixed page (scanned annex) | 53.3% | **100%** | — |
| Speed / peak RSS | 0.34 s/page · 0.25 GB | 0.31 s/page · 0.32 GB | 7.4 s/page · 1.8 GB |

Per document the fixed parser reads SLA-leapswitch, NDA and DPDP Rules tables 0 → 100%,
MSA-GRP's annexure table 0 → 89%. Numbers recall 96.6 → 95.9% is the Hindi scan only: OCR that
cannot read it now fails closed instead of storing gibberish that happened to contain digits.
OCRmyPDF was measured and not adopted (no better than direct Tesseract on scans; 4/15 on the mixed
page). Docling's whole-page numbers above are why it was tried; §2 is why it reads tables only.

**Docling tables-only, 13 approved PDFs:** prose and every page's word and character multiset
identical with Docling on and off; Docling's tables inlined on SLA-cloudpe pp. 1–2 (8×2 uptime,
4×2 credits, checked against the rendered pages); the gate sends 18 of 137 pages. A run costs
13–16 s / 1.26–1.47 GB for 1–3 pages, 40–71 s / 1.86–1.91 GB for 12 pages.

**Retrieval** (`tools.benchmark_document_lane`, 44 answerable contract questions, scratch DB,
`LEGALMIND_RERANK=on`, zero Gemini): gold clause in evidence 27 → 27, top-3 26 → 26, first
claim 23 → **24**, not-found questions answered from the document 0 → 0, none newly missed
(the SLA credit question rank 3 → 2). The table regression of 2026-09 does not recur.

**Real answers** (production Ask agent path, scratch DB, 9 questions, **32 Gemini calls**):
8 correct — SLA 15% at 99.2% uptime, SLA exclusions, CloudPe 20% below 95%, TOS 12-month cap,
MSA "Business Data" definition, the scanned annexure's 100% (read by OCR), a sideways scan's 15%,
a Word table's 40% (marked as a table). The ninth (MSA 17.2 vs 17.7) hit Gemini's time limit;
the fallback quoted 17.2 correctly.

## 4. Tests

New: `test_pdf_reading.py`, `test_docx_reading.py`, `test_docling_reading.py`,
`assist/agent/test_assist_document_gap.py`, `assist/agent/test_attachment_reading.py`,
`assist/ingestion/test_table_chunks.py`, `assist/knowledge/test_annex_attribution.py`,
`assist/synthesis/test_evidence_reading_order.py`, `frontend/src/__tests__/document-reading.test.ts`;
extended: cache, conversational offers, temporary review, deferred OCR, ingestion, pagination.
Sampled new tests fail against `HEAD` on behaviour (cross-cutting review); two chunking tests are
regression guards by design. The 16 real-Docling tests skip without Docling (CI, nightly) and pass
locally with it (94 of 94 with the PDF suite).

## 5. Not done, and why

| Item | Why | Recommended next step · effort |
|---|---|---|
| Word automatic list numbering (`w:numPr`) | Rendering it computes a number; locked 34.12 says numbering is preserved, never generated | Owner ruling: displayed numbering = the document's own · ~60 lines + tests |
| A clause continued on the next page is two evidence rows for the evaluator | Joining them changes the authoritative lane's input (a carve-out read with its cap) | Owner decision, then join a lowercase page-head continuation in `parse_pdf` · ~1 day with golden-corpus re-run |
| Page furniture firing the column reorder (R1) | Moves text embeddings were built from | Ignore top/bottom 8% in `_reads_in_columns`, re-measure with the document lane · ~2 h |
| PDF tables drawn with horizontal rules only (SLA-cloudpe) without Docling | PyMuPDF has no strategy for them | Enable Docling (§6) |
| Scanned tables | OCR text has no cells | Docling OCR tables with a tsv-geometry check · ~1 day |
| A table continued across pages | Two tables, the second without its header | Carry the header forward · ~2 h |
| Header row repeated in later chunks of a long table | A chunk must be a substring of its row (FABRICATED_TEXT) | Show the header at read time · ~2 h |
| A partial newest chat file falls to the agent with no fixed sentence | The model is told `pages_not_read` | Fixed text for "not reviewed: read in part" · ~1 h |
| The inline-OCR timeout leaves the first read running | Bounded by tesseract's own timeout | Move chat OCR to the worker if it bites |
| Docling child kept offline by environment only | No network namespace in the unit | Dedicated unit with `IPAddressDeny=any` · ~1 h |
| Real-Docling tests never run in CI | No Docling in CI or nightly | Nightly job that provisions Docling and fails if it does not load · ~2 h |
| One answer sentence (the annex's 100%) shipped uncited | Verifier behaviour, not reading | Investigate in the Ask lane |
| `assist_index_refused` written to the processing run from the assist lane | `preflight` says the assist role writes only its schema; the role is not used at runtime today | Record as an audit event instead if that role is ever enforced |

## 6. Rolling it out (owner, later)

1. **Merge and deploy as usual.** Docling stays **off** (both variables unset); every other fix
   is live on deploy. No migration.
2. **Enable Docling tables** (optional, separate step):
   - *Prerequisites on the host:* `tesseract` with `eng` and util-linux `choom` (both present on
     the production host today); ~1.7 GB disk for the venv, ~0.7 GB for the models.
   - *Install, in its own environment — never the API's:*
     `python3 -m venv /opt/legalmind/docling-venv` then
     `/opt/legalmind/docling-venv/bin/pip install -r ops/docling/requirements.txt`
     (Docling 2.139.0, CPU torch 2.14.1).
   - *Provision the models once (the only download; Docling then runs offline, `AM-30`):*
     `/opt/legalmind/docling-venv/bin/docling-tools models download -o /opt/legalmind/docling-models layout tableformer`.
   - *Memory — required before step 2e:* raise `MemoryMax` from `3G` to **`5G`** in
     `ops/production/legalmind-api.service.d/10-hardening.conf` (installed copy under
     `/etc/systemd/system/legalmind-api.service.d/`), then `systemctl daemon-reload`. Measured: the
     API peaks ~1.4 GB; a Docling run 1.26–1.47 GB for 1–3 table pages, 1.86–1.91 GB for 12 pages
     (the most one run is sent). The child runs under `choom -n 1000`, so if memory still runs out
     the kernel kills Docling (the document falls back), not the API.
   - *Switch on:* add `LEGALMIND_DOCLING_PYTHON=/opt/legalmind/docling-venv/bin/python` and
     `LEGALMIND_DOCLING_MODELS=/opt/legalmind/docling-models` to `/root/.legalmind.env`;
     `systemctl restart legalmind-api`.
   - *Check it ran:* upload a PDF with a table (SLA-cloudpe has two); the upload reads in the
     background ("Reading the document", ~15 s for 2–3 table pages); its latest processing run's
     metadata has `reader.docling_tables` listing the pages and a diagnostic "Docling 2.139.0 read
     tables on …"; the credit tiers show as `| … | 5% |` rows in the document pane.
   - *Rollback:* remove the two variables and restart the API — every PDF is read by the standard
     parser again; nothing else changes.
3. **Re-upload or reprocess** a document to read it with v5; nothing re-reads on its own (rule 17).

## 7. Locks

`AM-144` (AB-89, appended 2026-10-16): Docling as a table reader (owner), documents English
(owner), chat material OCR'd within bounds (amends `AM-133` r3), the background run carries a
table-only deferral. `AM-143` r5 restored after this work had briefly broken it. Locked 34.8–34.14,
rule 17, `AM-27` r4 and `AM-30` verified as holding by the cross-cutting review.

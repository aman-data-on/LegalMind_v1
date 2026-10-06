# Ask agent — owner decisions from audit A2, A4, A5 (one page)

**Status:** 📁 PROPOSAL, 2026-09-30. Evidence: [audit](ASK_AGENT_AUDIT_A1-A5_2026-09-30.md).
Already decided: attachments and the evidence ledger get **new tables**, not Contracts. The
table design is in [ASK_AGENT_TABLES_DESIGN_NOTE.md](ASK_AGENT_TABLES_DESIGN_NOTE.md).

| # | Decision | Options | Recommendation | Effect |
|---|---|---|---|---|
| **A2-1** | Executed vs draft (plan 1.15) | (a) Read the existing declared `version_role`; when it is absent → **unsigned**. (b) Also detect signatures from text. (c) Leave every chunk as `"DOCUMENT"` | **(a).** Detection (b) is a heuristic that could label a copy executed wrongly, which is the exact failure 1.15 forbids | Nothing is ever shown as executed unless a person declared it `FINAL_SIGNED`. Retrieval's authority label changes from `DOCUMENT` to executed/unsigned. That can change how evidence is judged, so it is measured on the document probe before merge |
| **A2-2** | Near-duplicate copies (plan 1.13) | (a) Side table with a deterministic group: a normalised-text hash plus a similarity threshold. (b) JSONB key on `document_versions.metadata`. (c) No grouping | **(a).** It is additive and leaves existing tables alone, per your rule. The threshold is a measured constant, not a legal value | Two copies of one agreement are cited as one agreement with two versions. Needs the migration in the design note |
| **A2-3** | `DRAFT` requirements reachable in positions search | (a) Exclude `DRAFT` as well as `DEPRECATED` (`positions.py:571`, `:717`). (b) Leave it | **(a)**, with a test. It is a two-word SQL change | An unratified draft standard can never be quoted in Ask |
| **A2-4** | Effective dates on positions | (a) Add one when a source states it. (b) Defer | **(b).** No supplied source gives these dates (rule 21) | None now |
| **A4-1** | Who may attach material to a chat | (a) `assist.ask` plus conversation ownership. (b) Also `document.upload` | **(a).** Material is conversation-scoped and never becomes a Contract | Any Ask user can paste or attach. It is visible to the owner's conversation only |
| **A4-2** | Retention | TTL in config: 30 / 90 days / until the conversation is deleted | **30 days**, `LEGALMIND_ASK_ATTACHMENT_TTL_DAYS`. A purge job deletes the text and its chunks | Pasted emails may hold personal data. Short retention limits exposure |
| **A4-3** | Limits | Per file and per conversation | 10 MB per file, 10 files per conversation, and pastes up to 200,000 characters. All configurable | Bounded storage and indexing cost |
| **A4-4** | Asking while a contract's document is still processing | (a) Say so in the answer, using the existing processing status. (b) Leave it silent | **(a)**, together with 1.2 attachment status | No silent "nothing found" |
| **A5-1** | Stable identity for evidence | (a) The ledger stores a **natural key** (standard code + version, Constitution section + source version, statute + section, chunk id for documents) plus a text hash. (b) Make position re-chunking keep IDs | **(a).** It survives a re-chunk with no change to existing tables. (b) can follow separately | A cited position no longer disappears when standards are re-imported. Today the foreign key's `ON DELETE CASCADE` silently deletes those citations |
| **A5-2** | The multi-source path saves the wrong citation list (`service.py:1530-1534`) | (a) Save the refs the answer actually cited, into the ledger. (b) Leave it | **(a)**, in Phase 1C | The replay and audit trail match what the reader saw |
| **A5-3** | No column for Constitution citations | (a) Record them as ledger rows (class `C`). (b) Add a column to `answer_citations` | **(a).** It leaves existing tables alone | Constitution citations become first-class, not JSON in `retrieval_runs` |
| **Fix 4** | The rescue Gemini call inside retrieval writes no audit row | See below | Implement as proposed | Every paid call appears in `audit_events` against its request |

## Fix 4: proposal, not yet implemented

**Now.** The rescue judge goes through the egress seam, which counts and logs it, but no
`assist.generation_called` row is written for it on either path:

- **Multi-source path:** `retrieval._search` calls `rescue.reconsider(refused, question)` with
  no `request_id` (`retrieval.py:177`). Its `_recorded` wrapper (`service.py:1453`) wraps only
  the generation calls.
- **Legacy path:** `service.py:931` passes `request_id`, so the log line carries it, but
  `_audit_calls` is never given the result.

**Change**, roughly 15 lines with no new abstraction:

1. `rescue.rescue_indices` and `rescue.reconsider` take `on_call: Callable[[GenerationResult], None] | None = None`
   and invoke it with the `GenerationResult` right after `generate_raw` returns.
2. `retrieval.candidates(..., request_id=None, on_call=None)` passes both through `_search` to
   `reconsider`.
3. The multi-source path passes `on_call=calls.append` and `request_id`. The existing
   `_audit_calls` (`service.py:1572`) then writes the row. It runs on the fallback branch too,
   so a rescue that happens before a failure is still audited.
4. The legacy path collects into a local list and calls `_audit_calls` beside its generation
   audit.

**Test.** Stub `generation.generate_raw` to return a fixed result, shut the gate, and ask once on
each path. Assert exactly one `assist.generation_called` row carrying `RESCUE_PROMPT_VERSION`
and the request's id, and no payload text.

**Unchanged:** no prompt, no gate threshold, no calibration constant, no change to when the
rescue runs.

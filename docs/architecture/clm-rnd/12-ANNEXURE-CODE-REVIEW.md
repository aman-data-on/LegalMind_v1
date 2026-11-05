# CLM R&D — 12 · Special Conditions annexure: code review

`📁 ANALYSIS` 2026-11-04 · code-review agent (fresh eyes, read-only) · scope: uncommitted `backend/` in worktree `clm-p1` (HEAD `820455d7`) against design `11-ANNEXURE-SYSTEM-DESIGN.md` §1–§12. Frontend not reviewed.

How I verified: I traced each code path end to end. I ran `tests/drafting/test_special_conditions.py` on a fresh DB (`lm_review_sc_20261104`): 13 passed, 1 skipped (no LibreOffice). I also ran a throwaway probe that reuses that module's fixtures; it was deleted afterwards and no repository file was changed.

## Findings, most severe first

### H-1 · The effective reading finds clauses by number only. A renumbered body crashes it or applies an entry to the wrong clause.
`legalmind/analysis/effective.py:151-161` (validation), `:186-199` (`_rewrite` spans).
- **What fails:** the client returns the package with one body sub-clause deleted or added. Word auto-numbering renumbers everything after it.
  - `_rewrite` looks up `spans[e["number"]]`, and that number no longer exists in the raw body, so it raises `KeyError`.
  - Only `_NotApplied` is caught. The exception therefore escapes `effective_clauses` and reaches `negotiation.changes` (the change list for that contract fails) and `run_analysis`.
  - **Confirmed by probe:** I deleted body 4.1 from v3 and ingested it as v4. Result: `KeyError: '4.2'` at `effective.py:197`.
- **When the target number still exists after renumbering:** the entry is applied to a different clause, the one that now has that number.
  - The only identity check is the heading. Sub-clauses without a run-in title have `None == None`, so the check passes.
  - The real clause text then disappears from the effective contract. A Requirement measured on that clause reads it as missing, or the change is reported against the wrong clause (rules 11 and 15).
- **Fix:**
  - In `_apply`, check that every entry's number is in `spans` and raise `_NotApplied` if one is not.
  - Check that the raw row at each span start still reads like the base target's `lead`, or anchor on the REF bookmark instead of the number. Raise `_NotApplied` on a mismatch.
  - Wrap `_apply` so that any unexpected exception becomes `NOT_APPLIED` with a reason, never a 500.

### M-1 · Two inserts after the same clause come out in reverse order
`effective.py:197-215`.
- **What fails:** the client adds two consecutive paragraphs after 17.2. `derive` produces 17.2A and then 17.2B, both anchored on 17.2. `_rewrite` sorts them with equal keys and inserts each at `out[j:j]`, so B lands in front of A.
- **Confirmed** by calling `_rewrite` directly: `[4.1, 4.2, 4.2B, 4.2A, 5]`. The effective contract, and so the Findings and the diff, read the clauses out of order. This breaks the determinism and order guarantee of §2.
- **Fix:** insert the inserts for one anchor in reverse `n` order, or keep a running offset.

### M-2 · Every later version in a contract that has a package must carry the annexure, or its analysis fails
`effective.py:62-73, 118-121`; `service.py` refusal.
- **What fails:** `_frame_version` uses "the latest earlier package in the contract" for any later version, whether or not that version came from the package. After a package exists, each of these reads `NOT_APPLIED`, and `run_analysis` then fails with `ANALYSIS_FAILED`:
  - the client's own paper,
  - a retyped copy,
  - an OCR'd signed scan,
  - a copy from which the client removed the annexure.
- This changes behaviour for third-party paper inside such contracts, and nothing can recover the contract except a person.
- **Fix:** when the copy has neither the frame title nor the precedence wording, read it raw (`NONE`): a document without the annexure says only its body. Keep `NOT_APPLIED` for a copy where the annexure is present but does not read as approved.

### M-3 · An answer written during the POST is not locked out
`api/routers/negotiation.py:1138` takes `FOR UPDATE` on the contract row. `answer_change` (`:463`) takes no lock.
- **What fails:** an answer committed after the POST has read the answers is not in the package. The round is then closed by `_replied_in`, so the stored trace points at a superseded choice.
- `prepare_reply` (`:805`) has the same pre-existing pattern. `STALE_PREVIEW` only covers the gap between the dry run and the POST.
- **Fix:** take the same contract-row lock in `answer_change` (and in `keep_ours_on_formatting`) before `_replied_in`.

### L-1 · SC_TRACE accepts any effective Legal Decision
`negotiation.py:1088-1093, 1109-1124`.
- `decision_ids` collects every effective decision, whatever its type. A REJECT therefore satisfies "the Legal Decision that accepted it", which is what the docstring promises.
- Today `_holder_accepted` (`_ACCEPTING`) backstops this through `_reply_blockers`. The annexure's own R-12 check, however, cannot stand alone, and its unit test passes `["d"]` without saying which decision type that is.
- **Fix:** filter by `_ACCEPTING`, or by `_approves(wording_sha256)` for our wording.

### L-2 · The holder-answer audit used for the trace may belong to a replaced answer
`negotiation.py:1094-1098`.
- The query takes the latest `NEGOTIATION_HOLDER_ANSWERED` for the row key. It does not check that this audit row belongs to the current choice: after a holder's answer is replaced by a non-holder's, the old audit row still satisfies SC_TRACE.
- **Fix:** match `after_state.answer_version == choice.version_number`.

### L-3 · Decisions now carry across every reply round regardless of row order
`workflow/decisions.py:340` `_hash_rows`.
- Rows are now hashed in sorted order for every reply round, not only for packages. A Legal Decision now carries onto an Evaluation that reads the same paragraphs in a different order. This widens decision carry beyond what the annexure needs.
- **Fix:** sort only where `package_of` is set, or keep the document order and move only the annexure rows.

### L-4 · Varied-clause headings are exempt from the defined-term check everywhere
`drafting/preflight.py:272`. The quoted headings of varied clauses are added to `roles`. That exempts those words from UNDEFINED_TERM across the whole document, not only inside the leads.
- **Fix:** exempt them only inside the `lm:special-conditions` sdt.

### L-5 · STALE_PREVIEW does not cover the lead wording or the answer behind an entry
`special_conditions.py` `entries_sha256`.
- The hash leaves out the frame and precedence versions and the answer and effect of each entry. A re-approved frame between the dry run and the POST changes the lead wording without a 409.
- **Fix:** add the frame `clause_key@version` and the precedence version to the hash.

### Tests that are vacuous or missing
- **Byte identity is not guarded:** `test_without_special_conditions_the_model_and_bytes_are_unchanged` compares the new renderer with itself. "Bytes identical to before" was checked once by hand against `ca1d73ba` and is not pinned.
- **The PDF test always skips here:** it skips unless `LEGALMIND_SOFFICE` is set, and `soffice` is not installed on this host. None of SC_NEW_PAGE, the PDF xrefs or the continuous page run ran in this review.
- **Not covered at all:**
  - a client-edited annexure (handled correctly by probe: it surfaced as a HOLDER row),
  - a renumbered body (H-1),
  - two inserts (M-1),
  - `before_execution`,
  - the 409s on `/content`, `/pdf` and `mark_sent` for a package (only `reply_open_points` is called directly),
  - SC_TRACE through the endpoint with a measured NEGATIVE change,
  - 404 body identity: the tests check only the status code.

## Checked and found sound
- **Gates:**
  - `/content`, `/pdf` and `mark_sent` all go through `reply_open_points`, and `answers()` now includes `package_of`.
  - A missing or unanalysed Review fails closed.
  - Re-answering a closed round returns 409, because `_replied_in` matches `package_of`.
  - LATER_ROUND and REDLINE_ROUND block packages.
  - BODY_CHANGED rebuilds the body from the template and compares it with the stored `model_hash`.
- **Our own package:** a tampered package fails on the trace hash (`NOT_APPLIED` → `ANALYSIS_FAILED`, tested).
- **The client's copy:** it is read without the trace, but its changes surface as HOLDER rows. Probe: an edited entry showed as `MODIFIED 5 holder`. The signed copy is compared raw.
- **Evidence:** `_rewrite` keeps the evidence ids (`dataclasses.replace`).
- **SEC-07:**
  - `internal_note` is omitted without `legal_position.view`, the same as `answer_lines`.
  - The trace is not serialised by `declared_metadata`, and no router returns raw `doc_metadata`.
  - The new endpoints are in `permission_map`.
  - The audit event `contract.package_prepared` carries ids and hashes only, no notes.
- **Frame and precedence:**
  - Both are imported as DRAFT only (`attach_special_conditions` refuses a non-DRAFT template).
  - Readiness requires both to be APPROVED, and publishing requires the frame to be APPROVED (`pin_list`).
  - The opening sentence and the deletion lead are engineering-composed reference text. They are labelled "For management approval" and are never APPROVED. The lawyer must still approve them (Q-3, Q-4).
- **Records:**
  - No migration and no schema change.
  - `clm-records/all_lock.md` against `origin/main` is a pure append: 0 removed lines, and the first 27678 lines are byte-identical.

## Review fixes (backend agent, 2026-11-04, worktree `clm-p1`, uncommitted)

Each fix has a regression test in `backend/tests/drafting/test_special_conditions.py`. The five behavioural ones (H-1, M-1, M-2, M-3, L-2) were run against the code with the fix reverted and failed there.

| Finding | Root cause → fix | Test |
|---|---|---|
| H-1 | `_rewrite` trusted the number. Every entry's span must now exist AND its first row read as the base target's lead (`special_conditions._norm`), else `_NotApplied` ("renumbered or changed"); any unexpected error in the reading becomes NOT_APPLIED with its type, logged `analysis.special_conditions.unreadable`, never a 500 | `test_a_renumbered_body_is_never_read_as_another_clause` (4.1 deleted, Word renumbers: NOT_APPLIED, change list all HOLDER) |
| M-1 | equal sort keys; inserts on one anchor now applied last-first | `test_two_insertions_after_one_clause_keep_their_order` |
| M-2 | a later copy without the annexure now reads `ABSENT` ("Special Conditions not found in this copy"): raw rows, analysis runs (logged), the change list says so and routes every row to a person. Our own package without it stays NOT_APPLIED. `execution.compare` stays raw | `test_a_later_copy_without_the_annexure_is_read_raw_for_a_person` |
| M-3 | `_lock` (contract row `FOR UPDATE`) taken first by `answer_change`, `keep_ours_on_formatting`, `accept_by_effect`, `prepare_reply` and the package POST | `test_every_answer_takes_the_contract_lock_a_package_takes` (the lock precedes the write) |
| L-1 | `_lets_stand`: only ACCEPT_DEVIATION / NOT_APPLICABLE_TO_CONTRACT, or an APPROVE_CUSTOMIZATION of exactly this wording, enter `decision_ids` | `test_an_entry_worse_for_us_needs_the_decision_that_accepted_it` |
| L-2 | the holder-answer audit must carry `answer_version` = the current choice's | `test_a_holder_answer_counts_only_while_it_is_the_current_answer` (→ SC_TRACE 409) |
| L-3 | order-free row hashing only where the version is a package; a tracked reply keeps the document order. Wording substitution matches the answer's own row key | `test_carried_rows_are_order_free_only_for_a_final_contract` |
| L-4 | headings exempt from UNDEFINED_TERM only in paragraphs inside `lm:special-conditions` | `test_a_varied_clauses_heading_is_exempt_only_inside_the_annexure` |
| L-5 | `entries_sha256` covers the frame and precedence `key@version` and each entry's answer and effect | `test_the_preview_hash_covers_the_frame_and_the_answers` |
| Tests | the byte-identity test compares with `tests/drafting/render_baseline.json`, generated from ca1d73ba's renderer, model and house.json (`git show`); the PDF test runs locally with `LEGALMIND_SOFFICE` and its CI skip reason says so | — |

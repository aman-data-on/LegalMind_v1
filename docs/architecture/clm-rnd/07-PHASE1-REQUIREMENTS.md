# Phase 1 — Negotiate and decide: requirements and acceptance tests

`PROPOSAL` — 2026-11-02. This is the requirement set for Phase 1 of [06-IMPLEMENTATION_PLAN.md](06-IMPLEMENTATION_PLAN.md).
It is built locally only (`feat/clm-p1-negotiate`, worktree `/root/legalmind-worktrees/clm-p1`, API :8399, UI :3399,
scratch DB `legalmind_clm_e2e`). It authorizes nothing beyond the owner-confirmed amendment batch AB-150.

## Who uses it

| Person | Account on the local stack | Can |
|---|---|---|
| Contract owner (salesperson) | `owner@e2e.test` | Upload the client's returned copy, see every change, answer non-legal changes, ask a holder about legal ones, prepare the reply |
| Holder of the right (test stand-in until the owner names the real one) | `counsel@e2e.test` | Everything above, plus accept the client's change on a ratified position or approve other wording — a recorded Legal Decision |
| Department Lead | `admin@e2e.test` | Publish standards; sees the department's deals |
| Position-blind reader | `reader@e2e.test` | Proves that internal positions are omitted, not greyed |

## Test material (local only, never in the repo)

`/root/legalmind-clm-fixtures/` (see its `MANIFEST.md`): client A's MSA in three rounds (r1 review, r2, r3) and the
clause-wise review with 15 comments; NDAs from clients B to F. **None of the Word files carries tracked changes.** Each is a
clean copy, so round 2 → round 3 of client A is the real-world case the untracked-edit check must catch. Names never
appear in any file, test name or log line ("client A").

## Requirements

Each requirement is written as *what the user gets*, then the *acceptance test* that proves it.

### R1 — Every change, in one list (WP 1.2)
- Upload a client's next version of a contract → a **Changes (n)** tab lists every difference from our previous version
  once, in document order, each typed **modified · added · deleted · moved · new annexure** and tied to its clause number
  and heading.
- **Test:** client A r2 → r3 lists every changed clause. A clause moved without edits is one "moved" row. Re-uploading
  the same file twice lists 0 changes.

### R2 — Changes the client did not mark are caught (WP 1.3)
- If the returned copy differs from what we sent without a tracked change, each such change carries **"changed without
  tracking"** and the tab shows a banner with the count.
- **Test:** on client A r2 → r3 (clean copies), every change is flagged this way. On a synthetic DOCX we generate with
  tracked changes, only the untracked edit is flagged.

### R3 — Each change says what it means for us (WP 1.2, 1.5)
- Each row shows the review's own status word for the clause (*Matches our standard · Change needed · Missing · Needs a
  decision*), quoted from the review of that version and never re-derived. It also shows what changed since our last
  version's review (the review delta), and "Explain this", assembled by code from the review's sentences.
- Our position appears only to people who may see positions. For everyone else it is **absent**, never greyed.
- **Test:** the status word equals the Finding of the same clause in the recorded Review. `reader@e2e.test`'s HTML
  contains no position text.

### R4 — The right person answers (WP 1.4)
- **Non-legal change** (names, addresses, typos the engine confirms change no measured value): the contract owner may
  *Keep ours* or *Accept theirs*.
- **Change on a ratified position, on a topic with no position, or not mapped with confidence:** the contract owner may
  *Keep our position* or *Ask someone with the right*. A **holder** sees *Accept theirs* (a recorded `ACCEPT_DEVIATION`)
  and *Our other wording* (a recorded `APPROVE_CUSTOMIZATION`) and decides **in place**. A second person is required where
  the standard sets it.
- **In our favour** (`AM-239`): the owner may accept, and the reason is shown.
- Anything not positively shown non-legal goes to a holder (fail closed).
- **Test:** `owner@e2e.test` has no accept control on a position change (absent from the DOM). `counsel@e2e.test`
  accepts it, and a `legal_decisions` row exists with the reason. A standard with `requires_second_person` stays undecided
  after one signature.

### R5 — Answers have history (WP 1.1)
- Every answer records who, when, the answer and an optional one-line reason. Each later answer is a new row. A change
  shows its line: *"R1: kept ours (owner, 24 Oct) → R2: accepted theirs (Legal Decision, counsel, reason …)"*.
- A stale answer (someone answered a minute ago) gets *"changed by a colleague — reload"* (409), never a silent
  overwrite.
- **Test:** three rounds produce three history entries. UPDATE and DELETE on the table are refused by the trigger.
  Diff-Talk's existing tests pass unchanged.

### R6 — Our reply, as a Word file with our tracked changes (WP 1.6)
- *Prepare our reply* takes the client's own DOCX and applies our answers as **tracked changes** authored "LeapSwitch
  Legal". Keep ours restores our wording as an insertion and deletion; accepted changes are left as the client wrote
  them. It also produces a PDF. The reply becomes the next version (`COMPANY_DRAFT`) and is reviewed by the same engine.
- The server refuses (409) while any departure **we** proposed is undecided.
- **Test:** the reply opens in Word and LibreOffice. Parsing it back yields exactly our tracked changes, no more and no
  fewer. The 409 test passes.

### R7 — Where every deal stands (WP 1.7)
- Each contract shows one stage in the header and on the list: *Drafting · Internal review · With client · Client returned
  (our turn) · Ready to sign · Signed*. The stage is derived, never typed in, and *Mark sent* records when it went out.
  The list is called **Contracts**, and links read `/contracts/{id}`, `/contracts/{id}/changes`.
- **Test:** each fixture path lands on the right stage. Old `/dashboard?id=` links redirect. An out-of-scope id returns a
  byte-identical 404.

### R8 — My work, in one place (WP 1.8)
- **To-do** lists what is waiting on *me*: decisions I can make, second approvals I owe, client returns on my deals, and
  answers to my requests.
- **Test:** each persona sees only its own items.

### R9 — Told when it matters (WP 1.9)
- In-app notifications and an e-mail: *asked you to decide*, *decided*, *client returned a new version*. A message
  carries a link and a fixed sentence, never clause text. Locally, e-mail goes to a file.
- **Test:** the sink holds the expected messages, and a grep for clause text finds none.

### R10 — Colleagues and Ask (WP 1.10)
- The owner can add same-department collaborators who may answer changes and upload returns. In Ask, *File this into
  the contract* attaches a returned copy as the contract's next version, and only when the user presses it.
- **Test:** a non-collaborator's write returns 404, and Ask never creates a version on its own.

## Never (checked in every work package)

- The system never accepts a deviation by itself. ACCEPTABLE comes only from MATCH or `AM-239`.
- No probability, confidence or "AI thinks" anywhere.
- No internal position reaches a client file, an e-mail or an out-of-scope reader.
- Uploaded-contract reviews are unchanged: the golden corpus and the Diff-Talk, client-changes and triage suites pass
  as they are.
- Nothing runs against the live server.

## Build order

R5 → R1 → R2 → R3/R4 → the Changes tab UI → R6 → R7–R10. The first batch for the owner's "go" is **R5, R1, R2, R4 (backend)
and the Changes tab**, which is enough to answer client A's real round-3 changes on :3399.

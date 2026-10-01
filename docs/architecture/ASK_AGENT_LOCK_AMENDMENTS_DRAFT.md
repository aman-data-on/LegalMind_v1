# Ask agent — draft lock amendments (APPLIED 2026-10-01)

**Status:** ✅ **APPLIED.** Owner-approved under D13 (2026-09-30) and appended to `all_lock.md`
on 2026-10-01 as **AB-61: `AM-111`, `AM-112`, `AM-113`** (`AM-110` went to the six tables,
AB-60). The appended record is authoritative and differs from the drafts below in one
place: owner decision D12 removed the provider-terms precondition from draft 3's t4' and
allows party names. This file is kept as the drafting record.

- **When:** on approval, each record is appended to the end of `all_lock.md` verbatim (rule 22).
  `LOCKED_DECISIONS.md`, `IMPLEMENTATION_STATUS.md` and every affected document are updated in the
  same change.
- **Numbering:** `AB-60` / `AM-110`–`AM-112` are placeholders. The last assigned numbers are
  `AB-59` / `AM-109`. Other sessions may take the next numbers before merge, so they are
  confirmed then.
- **Scope:** these records affect **agent mode** (`ASK_AGENT_MODE = shadow | on`, plan §7
  Phase 3) only. The current pipeline stays bound by today's wording, so rollback (flag `off`)
  needs no lock change.

## What each draft changes, and what already amended it

| Draft | Locked term, current effective state | Earlier narrowing — kept |
|---|---|---|
| `AM-110` | `AM-58` r1/r2 (prior USER questions only, never an earlier answer), which is itself a narrowing of `AM-30` t2 | `AM-58`, `AM-67` (position spans), `AM-89` (parent context, [A]/[M] lines) |
| `AM-111` | `AM-25` r5, **never amended since 2026-08-24**. Ten later records say explicitly that they leave it untouched | none |
| `AM-112` | `AM-30` t2, t3, **and t4** | t2: as above. t3: `AM-49`, `AM-67`, `AM-89` |

⚠️ **Scope correction on the owner's list.** The owner named `AM-30` t3 for pasted client
material. The conflict that binds is **t2**, a closed allow-list with no user material in it, and
**t4**: *"No counterparty name, signatory name, contract identifier … is included in an egressing
payload"*. A pasted contract or email always contains those. t3 is engaged only when the pasted
text quotes an internal legal position. `AM-112` therefore amends all three and names each.

---

## Draft 1

```text
# AB-60 — `AM-110` — Agent mode: earlier replies as labelled conversation context (Owner Instruction — <date>)
```

**Amends:** `AM-58` r1 (last sentence) and r2, for agent mode only, and through them `AM-30`
t2. **Does not amend:** `AM-58` r3–r7; `AM-30` t1, t3–t10 (as amended by `AM-67`, `AM-89` and
`AM-112`); `AM-25` r1–r9 (as amended by `AM-111`); `AM-89` ("never convert user assertion into
evidence"); rules 7, 12, 21.

**Why this record exists.** v2.1 §4.2 and plan task 3.4 send the thread window with *"earlier
assistant answers labelled as prior replies, not evidence"*. `AM-58` r2 forbids exactly this:
*"NEVER AN EARLIER ANSWER. An assistant turn is not evidence."* `AM-58`'s own engineering note
records the cost of that rule: *"is the 30 days you mentioned business days?"* may miss. The
agent's follow-up depth (G8) depends on reading the previous reply.

**Exact wording changes.**

`AM-58` r1, last sentence. Current: *"Nothing else about the conversation is admitted."*
Proposed: *"Nothing else about the conversation is admitted, except in agent mode as `AM-110`
r1 permits."*

`AM-58` r2. Current: *"NEVER AN EARLIER ANSWER. An assistant turn is not evidence. Admitting one
would let text that was itself generated ground a later claim, which is exactly what `AM-25`
r5's mechanical verification exists to prevent."* Replaced, **in agent mode only**, by:

```text
r1   AN EARLIER REPLY IS CONTEXT, NEVER EVIDENCE. In agent mode, the assistant
     turns of the SAME conversation may be sent, inside a token budget, each
     delimited and labelled "prior reply — not evidence". Outside agent mode
     `AM-58` r2 stands unchanged.

r2   NOTHING IS VERIFIED AGAINST A PRIOR REPLY. Every sourced block cites a
     ledger record fetched from its source; the verifier (V1–V4) checks a claim
     against that record's text only. A prior reply is never a ledger record,
     never cited, and never quoted as a source.

r3   A PINNED CLAUSE IS RE-FETCHED, NOT REMEMBERED. An ID a prior reply cited
     re-enters the turn only through re-fetch by ID under the caller's current
     permissions, marked `stale` when superseded and `unavailable` when no longer
     visible (plan 1.8).

r4   THE PRIOR REPLY IS SCREENED LIKE THE QUESTION. `AM-30` t3/t4 and `AM-58`
     r3/r4 apply to it exactly as they apply to a prior question.
```

---

## Draft 2

```text
# AB-60 — `AM-111` — Agent mode: sourced claims verified, other blocks labelled; no bare refusal (Owner Instruction — <date>)
```

**Amends:** `AM-25` r5, for agent mode only. **Does not amend:** `AM-25` r1–r4 and r6–r9. r4
stays in full: *"does this document meet our standard?"* still belongs to the evaluator, and no
assessment word is ever applied to it. Also not amended: `AM-28` r2; `AM-69` (language is not a
safety boundary); `AM-109`'s refusal rules for the pipeline; rule 12 (no probability, no
confidence); rule 7.

**Why this record exists.** Owner decisions D1–D4 (plan §2) allow the following, each of which
r5 forbids today:

- a labelled general explanation (L4) with no citation;
- the words `supported` / `contradicted` / `not_established` / `undeterminable`;
- reasoning on user-supplied facts;
- answers longer than three sentences.

r5 currently reads: *"No answer reaches a user unless every claim in it resolves to retrieved
evidence. Enforcement is mechanical and sits outside the model. Where evidence is insufficient,
the response is an explicit statement that the information was not found. A guess, a hedge, a
partial answer presented as complete, or a cached substitute is a defect."*

**Exact wording change.** In agent mode, r5 reads:

```text
r5   No SOURCED claim reaches a user unless it resolves to retrieved evidence.
     A sourced claim is any statement of what a company source, statute or
     document says; it cites ledger records, and the verifier (V1–V4) checks it
     against their text mechanically, outside the model.

r5a  A block that makes no source claim — reasoning, next step, user-stated,
     clarifying question, general explanation — may reach a user only in its
     labelled kind. It carries no attribution to a company source (V5), no
     company figure, and no citation it does not hold. A general explanation is
     labelled "General explanation, not a company position" and states no
     organisational position (r3 unchanged).

r5b  User-stated facts are premises, never evidence. Reasoning on them is
     conditional ("on the facts you describe"); they are never presented as
     established or as company policy (`AM-89` unchanged).

r5c  Assessment words describe a CLAIM against the sources available —
     supported, contradicted, not_established, undeterminable. They never
     state whether a document complies with a standard (r4), never carry a
     probability or confidence (rule 12), and never replace a Finding.

r5d  No bare refusal. Where sources are insufficient the reply says what the
     sources establish and what they do not (L2), asks one question (L3), or
     gives a labelled general explanation (L4). An unsupported sourced claim is
     still a defect; a partial answer is labelled partial, never presented as
     complete.
```

**Open point, flagged and not resolved here.** `AM-109` makes pipeline refusals identical across
causes. Agent-mode L2–L4 replies are not refusals, so `AM-109` is not engaged. A reply about a
document the caller cannot see must stay identical to a missing-document reply (`AM-25` r7,
v2.1 G10). The ladder must not turn an authorization refusal into a partial answer.

---

## Draft 3

```text
# AB-60 — `AM-112` — Agent mode: the requester's own material in the payload (Owner Instruction — <date>)
```

**Amends:** `AM-30` t2, t4 and t3, narrowly and for agent mode only. **Does not amend:**
`AM-30` t1 (the single egress seam), t5 (hash-only audit), t6 (no provider training), t7–t10;
`AM-58` r3 (a user can never smuggle a Company Standard value, Legal Rule, Finding or Rule Outcome
into a payload through pasted text); `AM-32` r4 as amended by `AM-67`; LEGAL-02 as a display rule;
owner decision D8 (no provider other than the approved one).

**Why this record exists.** Owner decision D5: *"Gemini receives pasted contract and email
text."* Three terms forbid that today:

- t2 is a closed allow-list: *"Only the requester's question and the retrieved chunk spans
  required to answer that one request may be sent, together with the prompt template."*
- t4: *"No counterparty name, signatory name, contract identifier, user identifier or
  organizational identifier is included in an egressing payload. A real counterparty is never
  named to a third party."*
- t3 forbids internal legal positions in a payload. Pasted text could carry one.

**Exact wording changes (agent mode only).**

```text
t2'  Added to the allow-list: spans of USER MATERIAL — text the requester pasted
     or attached in THIS conversation — required to answer the current request,
     each inside a delimited <user_material id=U…> block that the system contract
     names as data, never instructions. Never another user's material, never
     another conversation's.

t4'  User material may name counterparties and signatories because the
     requester supplied it. The application adds no name, identifier or
     organisational identifier of its own to the payload, and none is taken from
     any record other than the requester's own material. Enablement for real
     client material requires the owner's confirmation of provider terms and
     data residency (plan 5.1; owner decision D5), recorded by date in this
     record before agent mode is switched on for it.

t3'  User material is screened by the same forbidden-key screen as the question
     (`AM-58` r3). Internal legal positions reach a payload only by the routes
     `AM-49`, `AM-67` and `AM-89` already permit — never inside user material.
```

**Retention and trace:** see the design note. User material is excluded from trace content, and
its retention period is set in config. Neither is a lock term today, so neither is locked here.

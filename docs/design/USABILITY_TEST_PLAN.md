# Usability Test Plan — think-aloud sessions

**Status: 📁 PLAN — Phase 5 of the UI/UX roadmap, prepared 2026-08-27 on owner instruction.**
Governed by [../../DESIGN.md](../../DESIGN.md); running the sessions requires the owner to
name the participants. Nothing here changes the product.

## Method

Five moderated think-aloud sessions, 30–40 minutes each, on a desktop/laptop screen (the
product's declared primary context — phone-width is explicitly not a V1 target). The
participant shares their screen, narrates what they are thinking, and the moderator does
not help unless the task is fully stuck for 2 minutes (note the moment, then unblock).
Sessions run against a **staging or e2e environment with synthetic fixture data only** —
locked 55.3: no real counterparty document may appear in a test session, and none exists
in the e2e database.

Record (with consent): screen, audio, moderator notes. No session recording enters the
repository.

## Participants

| # | Persona | Profile | Sessions |
|---|---|---|---|
| P1–P3 | **Legal Reviewer (power user)** | Reviews contracts as a daily task; holds `legal.decision`; keyboard-heavy | 3 |
| P4–P5 | **Business User (occasional uploader)** | Uploads a contract every few weeks; no decision authority; may not remember the UI between visits | 2 |

Three power users to two occasional users, deliberately: the zero-tolerance policy makes
the decision queue the highest-traffic surface, but the occasional user is where
un-signposted flows fail hardest — both must be observed.

## Tasks

Each task is read aloud verbatim. The moderator records: completion (unassisted /
assisted / failed), time, wrong turns, and every quote worth keeping.

### Task A — Upload and find deviations *(P1–P5)*
> "You've received a new MSA from a counterparty. Get it into LegalMind and find out
> where it differs from our approved positions."

Watch for: does the uploader understand **declaring the document type** (it is never
inferred)? Does the analyse step's queued state read as progress or as "is it broken"?
Does the needs-decision default view read as "what needs me" — or get mistaken for the
whole Review (the known risk on the "All findings" toggle)?

### Task B — Decide on a flagged clause *(P1–P3 only — requires decision authority)*
> "One of the findings needs a legal decision. Record one, with your reasoning."

Watch for: do they find the decision control at the **Evaluation** level, or look for a
Finding-level button that deliberately does not exist? Does the mandatory justification
read as bureaucracy or as the record it is? **Keyboard sub-probe (P1 at minimum):** open
the `?` help unprompted or after a hint; do `n`/`a` behave as they expect — and do they
correctly understand that `a` did *not* record anything?

### Task C — Ask the assistant and verify the citation *(P1–P5)*
> "Without reading the whole document: what does it say about termination notice? Confirm
> the answer is really in the document."

Watch for: do they trust the citation, and do they *check* it (click through / read the
excerpt)? When a follow-up question gets the refusal ("Information not found…"), do they
read it as the system working or as an error? Do they re-ask the same thing rephrased
(a distrust signal we specifically track)? Does anyone ask "how confident is it?" — and
what do they make of the retrieval score's plain number?

### Task D — Try to reach something you shouldn't *(P4–P5, then P1)*
> "Here's a link a colleague sent you [a review id belonging to another user]. Open it.
> Then try to find that review any other way."

Watch for: the byte-identical 404 must read as "doesn't exist," with **no cue that it
exists but is forbidden**. For P1 (who sees rule outcomes) vs P4/P5 (who don't), show the
same Evaluation and ask "describe what you see" — the omitted field must not register as
a gap, a bug, or a locked feature. Any participant saying "it looks broken for me" is a
finding to record, not to explain away.

## Observation checklist (per session)

- [ ] Document type declared without moderator help
- [ ] Queued analysis state understood as "in progress, safe to wait"
- [ ] Needs-decision vs All-findings toggle: noticed · understood · used
- [ ] Decision control found at Evaluation level on first attempt
- [ ] Justification written without prompting (and not pasted junk)
- [ ] `?` help discovered (unprompted / hinted / never)
- [ ] Shortcut `a`/`r` correctly understood as *prepare*, not record
- [ ] Citation actually verified, not just trusted
- [ ] Refusal read as correct behavior (not error, not failure)
- [ ] Re-asked a refused question rephrased (count)
- [ ] 404 on out-of-scope object read as nonexistence
- [ ] Omitted confidential field unnoticed (the pass condition is *silence*)
- [ ] Any moment the participant said "I don't know what it's doing" (timestamp each)

## Feedback form (participant, after the session)

Seven-point scales unless noted:

1. "I could tell what the system was doing at every moment." (1–7)
2. "When it said something was not found, I believed it." (1–7)
3. "I understood which actions were formal decisions and which were not." (1–7)
4. "The amount of information on screen was —" (far too little · right · far too much)
5. "What almost went wrong?" (free text)
6. "What would you remove?" (free text)
7. "Would you use this for your real work tomorrow — why or why not?" (free text)

## Analysis and exit criteria

Findings are written up in this directory as `USABILITY_FINDINGS.md`, each tagged
(persona, task, severity: blocker / friction / polish) and mapped to a concrete change or
an explicit "no change, here's why". **Success bar:** every P1–P3 completes Tasks A–C
unassisted; no participant misreads the refusal as an error; no participant detects the
confidential omission; zero occurrences of a participant believing a decision was
recorded when it was not (that one is a release-blocking finding if it occurs even once).

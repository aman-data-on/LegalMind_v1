# Independent verification of the critical fixes

**Status: 📁 RECORD.** This document decides nothing and specifies nothing. It records
how each critical guarantee was checked, by what mechanism, and what the check found.

Run them:

```bash
cd backend
python3 -m tools.verify_invariants        # the invariants, by other mechanisms
python3 -m tools.verify_reproducibility   # the 55.4 r3 / 55.5 release gate
```

Both run in CI (jobs 11 and 12), so these are continuous rather than one-off.

---

## What "independent" means here, and what it does not

Every guarantee below already has a test in `backend/tests/`. That is not the same as
being verified. **A test and the code it guards can share the same wrong assumption**,
and this repository has a documented instance: `test_each_axis_has_its_own_enum_type`
was recorded as fixed while the `current_schema()` predicate it needed was absent from
the query, so it passed alone and failed beside a sibling.

So each claim is re-checked by a *different mechanism* — raw SQL instead of the ORM,
real processes instead of in-process calls, a grep of real output instead of asking the
redactor what it would do.

**This is not third-party verification.** It is verification by a mechanism independent
of the unit test, which is stronger than "the suite is green" and weaker than "someone
else confirmed it". Nothing here makes anything `VERIFIED`, and `IMPL-01` condition 2
still governs: *conformance is verified against the locked corpus*, which as of 2026-08-18
is 16 `STRUCTURAL`, 9 `DOCUMENT_SUPPORTED` and 3 `STANDARD_DERIVED` fixtures with **no
`NORMATIVE` fixture authored**. Two assert `MATCH` against the ratified Company Standard,
but **no fixture asserts any Rule Outcome but `NOT_APPLICABLE`**, because no Legal Rule
exists — un-ruled deviations are routed to a human instead, which is fail-closed but is not
conformance.

---

## Results — 2026-08-17

| Claim | Mechanism | Result |
|---|---|---|
| EV-MIN at insert (AB-1.6) | Raw `INSERT` of a Finding with no Evaluation, outside the ORM and outside pytest | **PASS** — refused at `COMMIT` |
| EV-MIN on delete (`F-1`) | Raw `DELETE` of the last Evaluation | **PASS** — refused at `COMMIT` |
| EV-MIN on re-parent (`F-1`) | Raw `UPDATE` moving an Evaluation to another Finding | **PASS** — refused at `COMMIT` |
| Append-only audit trail (`AUD-01`) | Raw `UPDATE` and `DELETE` on `audit_events` | **PASS** — both refused |
| Finding uniqueness (43.28) | Raw duplicate `INSERT` on `(review_id, requirement_version_id)` | **PASS** — refused |
| Enum scoping (`REC-06`, `F-4`) | Both queries run against **two live schemas** | **PASS** — unscoped counts 21, scoped counts 7 |
| Broker-less worker refuses (55.1) | A real `celery worker` process, exit code observed | **PASS** — exits non-zero and names the variable |
| Crash recovery (`acks_late`) | A real worker `SIGKILL`ed mid-batch, then recovery observed | **PASS after a fix** — see below |
| Duplicate delivery (43.28) | Two real workers competing over one Review, five deliveries | **PASS** — exactly one Finding, one Evaluation |
| 53.3 redaction | Grep of 188 real log lines from a browser-driven session (143 `http.request`, 15 each of the three `analysis.*` events) | **PASS** — none of the four forbidden classes present |
| Determinism (`ENG-11`, 54.3) | Two separate OS processes, different hash seeds, `tr_TR` locale and a `+14` timezone | **PASS** — byte-identical corpus output |
| Reproducibility survives migration (55.4 r3, 55.5) | A real `downgrade -1` / `upgrade head` round trip, then the historical record re-read **and** the same document + snapshot re-analysed | **PASS** — `python3 -m tools.verify_reproducibility`; identical digest before, after, and on re-analysis |

---

## What it found: `acks_late` was set, and recovery was an hour away

The first run reported **23 of 24 Reviews analysed** after a real `SIGKILL`. One looked
lost.

It was not lost, and the unit test was not wrong about what it asserted — it asserted
the wrong *kind* of thing:

```python
assert celery_app.conf.task_acks_late is True
assert celery_app.conf.task_reject_on_worker_lost is True
```

Both are true, and neither controls when a message comes back. The Redis transport
tracks delivered-but-unacked messages in a sorted set and restores one only after its
**visibility timeout**, and kombu's default is **3600 seconds**. A graceful stop
restores immediately, which is why every earlier test — all of which stopped workers
politely — passed. Only an abrupt death exposes it, and only against a real broker.

The consequence in production terms: a worker crash would leave that Review looking
stuck for an hour, with no error anywhere.

**Fixed** in `legalmind/worker/app.py` by deriving `visibility_timeout` from
`task_time_limit` (limit + 60s) so the two cannot drift, and the reason is written where
the setting is. It must stay *above* the task time limit: a shorter timeout would
redeliver a job that is still running, and two workers analysing one Review would
collide on `UNIQUE(review_id, requirement_version_id)` — correct, but wasteful.

`test_worker.py` now asserts the **relationship** rather than the flags, and says why it
exists. The verification run shortens the task time limit so the derived timeout is
observable in bounded time; the production number is asserted as a relationship, never
as a duration.

---

## Also found while verifying

* **A worker consumed nothing, silently** — the broker was configured only on dispatch,
  which a worker never calls, so `celery -A legalmind.worker.app worker` came up on
  Celery's default `amqp://localhost`. The first guard was a `worker_init` signal
  handler, which cannot work: Celery signals swallow receiver exceptions by design. It
  is a bootstep now.
* **A truncated diagnostic** — the version-skew log line passed both fingerprints inside
  one prose field, and a real log read `[209 chars omitted]`. 53.3's length guard was
  right; the field was wrong.
* **`F-6`, the assignment gap** — writing the browser suite showed that no endpoint can
  create the `review_assignments` row that locked Step 24 r6 requires, so a Legal
  Reviewer can reach no Review at all. Nine backend test sites hide it by inserting the
  row with `db.add()`. Recorded in [IMPLEMENTATION_STATUS.md](../00-project/IMPLEMENTATION_STATUS.md);
  **not resolved**, because a new endpoint and a new permission are a specification
  decision.
* **An unfaithful corpus fixture** — a `FAILED`-extraction fixture claimed zero evidence,
  and the runner's `N-34` invariant refused it. Correctly: a failed extraction means a
  clause *was* mapped and could not be interpreted, so the evidence survives the failure.
* **A database error wrote contract text into an operational log** — `exc_info` was the
  one path that bypassed `redact_fields`, and a driver embeds the failing statement and
  its bound parameters in the message. Confirmed against a real `IntegrityError`, then
  fixed by rendering exceptions as structure (frames and type kept; the message cut at
  the payload marker and length-guarded). 53.3 and 53.4 are both satisfied rather than
  traded off.
* **Running migrations silently disabled application logging** — Alembic's `fileConfig`
  defaults to `disable_existing_loggers=True`, and migrations run in-process in the test
  harness, in both verification tools, and in any deployment that migrates from the
  application image. Nothing legal would have broken (53.1 makes logs non-authoritative)
  and nothing would have been observable either. Found because a test that logged after
  touching the database captured nothing at all.

Six of these seven were invisible to a passing test suite.

---

## What is still not verified, and cannot be here

* **No `NORMATIVE` corpus fixture exists.** Conformance to the locked legal
  specification is verified against the corpus (`IMPL-01` condition 2, `ENG-12`), and
  the corpus is `STRUCTURAL` only. Structural fixtures verify the algorithm; they assert
  nothing about whether the algorithm reaches the organization's legal conclusions.
* **No threshold is calibrated** (locked 35.10). The numbers in every fixture and every
  test are structural and carry no legal meaning.
* Both need the organization's real Company Standard and Legal Rule. The contracts
  supplied on 2026-08-18 closed part of the first requirement — nine fixtures were authored
  from them — but supplied nothing about what the organization will *accept*, which is what
  a `MATCH` or a Rule Outcome requires. It must be supplied and never manufactured
  (rule 21). See [../00-project/SOURCE_MATERIAL_INTAKE.md](../00-project/SOURCE_MATERIAL_INTAKE.md).

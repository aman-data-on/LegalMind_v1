# API contract snapshot

**Status: 📁 DERIVED — generated from the application, frozen here, drift-tested.** Not a
specification. The authoritative API contract is
[STEP_49_API_FINALIZATION.md](../05-architecture/STEP_49_API_FINALIZATION.md) (🔒); where
this snapshot and Step 49 disagree, Step 49 wins and the disagreement is a defect to report,
never a snapshot to regenerate quietly (CLAUDE.md rule 5).

| File | What it is |
|---|---|
| [openapi.json](openapi.json) | The OpenAPI 3 document `legalmind.api.app.create_app()` generates, keys sorted, frozen at the commit that last changed the API |

## Why a frozen copy exists

The application serves this document only when `LEGALMIND_ENABLE_DOCS` is set — an
unauthenticated schema is a reconnaissance aid beside 47.7's 404-over-403 posture, so it is
off by default and off in production. Serving and **freezing** are different acts. The frozen
copy is what a UI/UX phase designs against ("finalized backend contracts", owner directive
2026-08-26), it is diffable in review, and
`backend/tests/test_api_contract.py::test_the_committed_openapi_snapshot_matches_the_app`
fails the suite the moment the code and the snapshot disagree — so a contract change is
always a visible, named diff in the same commit as the code that made it.

## Regenerating

```
cd backend
python3 -m tools.export_openapi          # rewrite docs/api/openapi.json
python3 -m tools.export_openapi --check  # exit 1 if stale (what the test does)
```

Regenerate in the **same commit** as the API change, and check the diff against Step 49
before committing. An endpoint that appears here but not in 49.3's table is an
implementation addition and must be recorded as such in
[AUTO_MODE_DECISIONS.md](../00-project/AUTO_MODE_DECISIONS.md) — see
`legalmind/api/permission_map.py::IMPLEMENTATION_ADDED_ENDPOINTS`.

## What the snapshot deliberately does not carry

* The confidentiality rules — `LEGAL-02` fields are **omitted, not nulled**, for callers
  without `legal_position.view` (49.7 r4). A schema cannot express "present for some
  callers"; the tests do.
* Denial semantics — out-of-scope objects are byte-identical 404s (49.5 r1, `API-10`); the
  schema lists status codes, the tests prove indistinguishability.
* Which permission each endpoint requires — that is `permission_map.py`, asserted complete
  by `test_every_registered_route_declares_a_permission`.

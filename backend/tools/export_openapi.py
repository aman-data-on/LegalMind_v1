"""Freeze the API contract — `docs/api/openapi.json`, the artifact a UI phase designs against.

49.12 deferred OpenAPI generation to implementation and `app.py` serves the document
only when `LEGALMIND_ENABLE_DOCS` is set (an unauthenticated schema is a reconnaissance
aid beside 47.7's 404-over-403 posture). Serving it and FREEZING it are different acts:
a committed snapshot is diffable, reviewable, and — through
`tests/test_api_contract.py::test_the_committed_openapi_snapshot_matches_the_app` —
cannot drift from the code without a failing test naming the change.

The generated document is a convenience and never the specification. Where it and
`STEP_49_API_FINALIZATION.md` disagree, Step 49 wins and the disagreement is a defect
to report (CLAUDE.md rule 5), not a snapshot to regenerate quietly.

Run:  python3 -m tools.export_openapi          # rewrite docs/api/openapi.json
      python3 -m tools.export_openapi --check  # exit 1 if the snapshot is stale
"""

from __future__ import annotations

import json
import pathlib
import sys

SNAPSHOT = pathlib.Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi.json"


def current_schema() -> dict:
    from legalmind.api.app import create_app

    schema = create_app().openapi()
    # Stable output: FastAPI's dict order is insertion order, which follows router
    # registration — deterministic already, but sort keys so a diff shows a contract
    # change and never a reordering.
    return json.loads(json.dumps(schema, sort_keys=True))


def render(schema: dict) -> str:
    return json.dumps(schema, indent=1, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    text = render(current_schema())
    if "--check" in argv:
        if not SNAPSHOT.exists():
            print(f"MISSING  {SNAPSHOT} — run `python3 -m tools.export_openapi`")
            return 1
        if SNAPSHOT.read_text() != text:
            print(f"STALE    {SNAPSHOT} no longer matches the application. Review the "
                  "change against STEP_49_API_FINALIZATION.md, then regenerate with "
                  "`python3 -m tools.export_openapi` in the same commit.")
            return 1
        print(f"OK       {SNAPSHOT} matches the application")
        return 0
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(text)
    paths = sum(len(ops) for ops in current_schema()["paths"].values())
    print(f"WROTE    {SNAPSHOT}  ({paths} operations)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

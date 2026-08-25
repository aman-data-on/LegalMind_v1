"""The assistive AI lane — locked AB-3 (`AM-25`–`AM-29`) and AB-4 (`AM-30`, `AM-31`).

Everything in this package is **assist-only**. Read `AM-25`'s nine terms before adding
to it; they are locked constraints, not guidance. The four that shape this package's
structure most directly:

    r1  never produces a Finding, an Evaluation, a Finding Classification, a Rule
        Outcome, a Mapping State, a Legal Decision, or a Review Lifecycle transition.
    r2  never writes to the legal or configuration tables — enforced by a database
        role holding no INSERT or UPDATE grant, not by convention.
    r4  never answers "does this document meet our standard?" That routes to the
        deterministic evaluator or is refused.
    r6  authorization is applied BEFORE retrieval, inside the query, resolved
        server-side from the session.

The deterministic lane does not import this package, and
`tests/test_import_boundaries.py` fails if it ever does — by allow-list, so the rule
held before this package existed and needs no maintenance to keep holding.

This package reads `document_evidence` and writes only to the assist schema. Evidence
stays authoritative; a chunk is a derived, disposable view of it, and dropping the
whole assist schema loses nothing that cannot be rebuilt.
"""

"""Structured fact extraction — locked 44.10, 44.11, 44.17, 44.29, 44.30.

Layer 5 of the locked engine (44.2): the stage that converts relevant contract
language into the structured facts an evaluator compares. Locked 44.11 is emphatic
that this is **requirement-specific** — "There should not be one universal parser
trying to understand every legal concept" — so each Requirement gets its own
extractor module rather than a shared interpreter.

Locked 44.29 draws the line this package sits on:

    Configuration controls:  thresholds, allowed values, patterns, terminology,
                             rule parameters
    Python controls:         parsing algorithms, normalization, FACT EXTRACTION
                             ALGORITHMS, comparison semantics, evaluation
                             execution, conflict detection mechanics

So the *algorithm* lives here and the *patterns and terminology it matches* come
from configuration. Nothing in this package ships a cap phrase, a carve-out term, a
unit or a threshold: those are the organization's legal material and must be
supplied, never manufactured (rule 21).
"""

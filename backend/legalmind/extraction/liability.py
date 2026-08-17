"""Liability fact extraction — locked 44.10, 44.11, 44.17, 44.30; output 45B.4.

Converts mapped clause text into the locked ``LiabilityFacts`` contract. This is
`LIABILITY-001`'s extractor and nothing else's (44.11).

--------------------------------------------------------------------------
44.17 is the rule that shapes this module
--------------------------------------------------------------------------
Locked 44.17 is explicit that a clause carrying a general cap plus carve-outs must
**not** be flattened:

    LegalMind should not flatten this into:
        liability_cap = 6 months
    only.
    It should preserve:
        General Rule + Exceptions / Carve-outs

So a general cap becomes one ``Cap`` with ``cap_kind = PRIMARY`` and each carve-out
becomes its own ``Cap`` with ``cap_kind = EXCEPTION`` and a ``scope``/``scope_label``.
The downstream 45C machinery then evaluates each governed scope separately, which is
what makes the "hidden carve-out" case — a conforming aggregate cap masking an
unacceptable exception — visible rather than averaged away.

--------------------------------------------------------------------------
Nothing is guessed
--------------------------------------------------------------------------
Locked 44.24 and 45B.7: uncertainty is recorded, never resolved. Concretely:

* no ``extraction`` configuration      -> ``FAILED``  + diagnostic
* cap language found, magnitude not    -> ``UNKNOWN``  (never a value)
* unlimited language found             -> ``UNLIMITED`` (never a value)
* no cap language at all               -> no ``Cap`` for that clause
* some clauses read, others not        -> ``PARTIAL`` + diagnostics

``evaluate_numeric`` already turns ``FAILED`` into ``UNABLE_TO_EVALUATE`` (45B.7)
and an empty ``caps`` tuple into established absence (45C.15), so the fail-closed
paths need no new code downstream.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from legalmind.domain.enums import EvaluationKind, ExtractionStatus
from legalmind.evaluation.contracts import Cap, LiabilityFacts
from legalmind.mapping.engine import Clause
from legalmind.mapping.scoring import contains_phrase, normalize

# cap_status values — locked 45A §4 / 45B.4. Mirrored from numeric.py rather than
# imported to keep the extractor independent of the evaluator; both cite the lock.
FINITE = "FINITE"
UNLIMITED = "UNLIMITED"
ABSENT = "ABSENT"
UNKNOWN = "UNKNOWN"

# The reserved scope key for a general cap. 45C uses per-Requirement scope
# vocabulary (AM-8'), and this is the one value the extractor may supply itself
# because it names "the general rule" rather than any legal category.
SCOPE_GENERAL = "GENERAL"


@dataclass(frozen=True)
class ExceptionPattern:
    """One configured carve-out — locked 44.17's "Exceptions / Carve-outs".

    ``scope`` is the scope key the evaluator will group on; ``scope_label`` is what a
    reviewer reads. ``terms`` is the configured terminology that identifies it. All
    three are the organization's material, never inferred from the text.
    """

    scope: str
    terms: tuple[str, ...]
    scope_label: str | None = None


@dataclass(frozen=True)
class LiabilityExtractionConfig:
    """Patterns and terminology — locked 44.29's configuration half.

    Every field is data: phrases, terms, unit names. Nothing is a regex supplied by
    an administrator, because an admin-editable expression language would move
    extraction logic outside tested code and break the `ENG-10` guarantee.
    """

    # 44.30 "finite-state / rule-based extraction" — the phrases that mark a cap,
    # e.g. the configured equivalent of "shall not exceed".
    cap_phrases: tuple[str, ...] = ()
    # Terminology marking an uncapped liability.
    unlimited_phrases: tuple[str, ...] = ()
    # 44.30 "regex/pattern matching for structured values" — the unit names that may
    # follow a magnitude. Configured, so no unit vocabulary is assumed.
    units: tuple[str, ...] = ()
    # Terminology identifying what the cap is measured against (45B.4 `cap_basis`).
    # Locked 45B.4: "We should not assume equivalence between different bases."
    bases: dict[str, tuple[str, ...]] = field(default_factory=dict)
    # 44.17 — the carve-outs to preserve separately.
    exceptions: tuple[ExceptionPattern, ...] = ()
    # The scope key a general cap is recorded under.
    general_scope: str = SCOPE_GENERAL

    @property
    def is_usable(self) -> bool:
        """A cap cannot be recognised without cap or unlimited terminology."""
        return bool(self.cap_phrases or self.unlimited_phrases)

    @classmethod
    def from_config(cls, configuration: dict | None) -> LiabilityExtractionConfig:
        """Read the ``extraction`` block of a Company Standard (42.8 JSONB).

        An absent or empty block yields an unusable config rather than an error, so
        the caller can record ``FAILED`` with a diagnostic and let the evaluator
        produce ``UNABLE_TO_EVALUATE`` — which is the locked outcome (45B.7), not an
        exception for someone to catch.
        """
        block = ((configuration or {}).get("extraction") or {})
        return cls(
            cap_phrases=tuple(block.get("cap_phrases") or ()),
            unlimited_phrases=tuple(block.get("unlimited_phrases") or ()),
            units=tuple(block.get("units") or ()),
            bases={k: tuple(v) for k, v in (block.get("bases") or {}).items()},
            exceptions=tuple(
                ExceptionPattern(
                    scope=e["scope"],
                    terms=tuple(e.get("terms") or ()),
                    scope_label=e.get("scope_label"))
                for e in (block.get("exceptions") or ())),
            general_scope=block.get("general_scope") or SCOPE_GENERAL,
        )


def extract_liability_facts(
    clauses: list[Clause],
    config: LiabilityExtractionConfig,
) -> LiabilityFacts:
    """Extract liability caps from the clauses the mapping layer confirmed.

    Deterministic: same clauses plus same configuration produce byte-identical facts,
    including diagnostic order (`ENG-11`). Clauses are processed in the order given —
    the mapping layer has already ordered them deterministically.
    """
    if not config.is_usable:
        # Locked ENG-09 / 45B.7. Refusing here rather than "trying anyway" is what
        # keeps an unconfigured Requirement from producing a legal conclusion.
        return LiabilityFacts(
            caps=(),
            extraction_status=ExtractionStatus.FAILED,
            extraction_diagnostics=(
                "no liability extraction configuration was supplied; no cap or "
                "unlimited terminology is available to recognise",),
        )

    caps: list[Cap] = []
    diagnostics: list[str] = []
    unread_clauses = 0

    for clause in clauses:
        body = normalize(clause.content)
        if not body:
            unread_clauses += 1
            diagnostics.append(f"clause {_label(clause)} has no readable text")
            continue

        found = _extract_from_clause(clause, body, config, diagnostics)
        if not found:
            # Not a diagnostic: a mapped clause need not contain a cap. Locked
            # 45C.15 — absence never manufactures a position.
            continue
        caps.extend(found)

    if not caps:
        # Distinguish "read everything, found no cap" from "could not read".
        # The first is established absence, which 45C.15 lets the evaluator treat as
        # a legitimate position; the second must never be reported as absence.
        all_unreadable = bool(clauses) and unread_clauses == len(clauses)
        if all_unreadable:
            diagnostics.append(
                "no clause yielded readable text; extraction failed rather than "
                "reporting absence")
        return LiabilityFacts(
            caps=(),
            extraction_status=(ExtractionStatus.FAILED if all_unreadable
                               else ExtractionStatus.COMPLETE),
            extraction_diagnostics=tuple(diagnostics),
        )

    # 45B.7 / REC-05 — PARTIAL is recorded, not smoothed over: some of the mapped
    # provisions could not be read, so the fact set may be incomplete and the
    # evaluator must be able to see that.
    status = (ExtractionStatus.PARTIAL if unread_clauses
              else ExtractionStatus.COMPLETE)
    return LiabilityFacts(
        caps=tuple(caps),
        extraction_status=status,
        extraction_diagnostics=tuple(diagnostics),
    )


# --------------------------------------------------------------------------
# Per-clause extraction
# --------------------------------------------------------------------------
def _extract_from_clause(
    clause: Clause,
    body: str,
    config: LiabilityExtractionConfig,
    diagnostics: list[str],
) -> list[Cap]:
    """Extract every cap this clause states — general and carve-out (44.17)."""
    evidence = (clause.evidence_id,)
    results: list[Cap] = []

    # 44.17 — carve-outs first, so a clause that is *only* about an exception is
    # not also recorded as a general cap.
    matched_exceptions = [
        pattern for pattern in config.exceptions
        if any(contains_phrase(body, term) for term in pattern.terms)
    ]

    states_unlimited = any(
        contains_phrase(body, phrase) for phrase in config.unlimited_phrases)
    states_cap = any(
        contains_phrase(body, phrase) for phrase in config.cap_phrases)

    if not (states_unlimited or states_cap):
        return []

    magnitude = _find_magnitude(body, config.units) if not states_unlimited else None
    basis = _find_basis(body, config.bases)

    if states_unlimited:
        status, value, unit = UNLIMITED, None, None
    elif magnitude is not None:
        status, value, unit = FINITE, magnitude[0], magnitude[1]
    else:
        # Cap language without a recognisable magnitude. Locked 44.24: uncertainty
        # is recorded deterministically, never resolved into a number.
        status, value, unit = UNKNOWN, None, None
        diagnostics.append(
            f"clause {_label(clause)} states a liability cap but no magnitude was "
            "recognised in the configured units")

    for pattern in matched_exceptions:
        results.append(Cap(
            cap_kind=EvaluationKind.EXCEPTION,
            scope=pattern.scope,
            scope_label=pattern.scope_label,
            cap_status=status,
            cap_value=value,
            cap_unit=unit,
            cap_basis=basis,
            evidence_refs=evidence,
        ))

    # A clause naming carve-outs *and* a general cap yields both; a clause naming
    # only carve-outs yields only those. Recording a general cap in the latter case
    # would invent a position the clause does not state.
    if not matched_exceptions:
        results.append(Cap(
            cap_kind=EvaluationKind.PRIMARY,
            scope=config.general_scope,
            scope_label=None,
            cap_status=status,
            cap_value=value,
            cap_unit=unit,
            cap_basis=basis,
            evidence_refs=evidence,
        ))

    return results


def _find_magnitude(body: str, units: tuple[str, ...]) -> tuple[float, str] | None:
    """Locked 44.30 "regex/pattern matching for structured values".

    Recognises a number immediately followed by one of the **configured** units. No
    unit vocabulary is built in, and no word-number ("six") is interpreted: doing so
    would be inventing terminology that 35.4/44.29 place in configuration.

    Returns the FIRST match in document order so the result is deterministic when a
    clause states several magnitudes; a clause with more than one is reported as a
    diagnostic by the caller only if none matched at all.
    """
    if not units:
        return None
    alternatives = "|".join(
        re.escape(normalize(u)) for u in units if normalize(u))
    if not alternatives:
        return None
    # Digits with optional thousands separators and decimals, then the unit.
    pattern = re.compile(
        rf"(?<!\w)(\d{{1,3}}(?:,\d{{3}})*(?:\.\d+)?|\d+(?:\.\d+)?)\s*"
        rf"({alternatives})(?!\w)")
    match = pattern.search(body)
    if match is None:
        return None
    raw = match.group(1).replace(",", "")
    try:
        return float(raw), match.group(2)
    except ValueError:                                  # pragma: no cover
        return None


def _find_basis(body: str, bases: dict[str, tuple[str, ...]]) -> str | None:
    """What the cap is measured against — locked 45B.4 ``cap_basis``.

    Returns ``None`` when no configured basis terminology matches. That matters:
    locked 45B.4 says "we should not assume equivalence between different bases", and
    ``RuleConfiguration.basis_is_comparable`` treats a ``None`` basis as
    non-comparable, so an unrecognised basis fails closed rather than being equated
    with the Company Standard's.

    Keys are visited in sorted order so a clause matching two bases resolves the
    same way on every run (`ENG-11`).
    """
    for basis in sorted(bases):
        if any(contains_phrase(body, term) for term in bases[basis]):
            return basis
    return None


def _label(clause: Clause) -> str:
    return clause.section_number or str(clause.evidence_id)

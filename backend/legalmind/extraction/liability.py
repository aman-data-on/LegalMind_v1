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

# A bare heading is not a clause — mirrors `assist/chunking.py::_is_heading`'s
# narrow judgment (one line, short, not a sentence) without importing across
# the authoritative/assist boundary (AM-25 r2).
_HEADING_MAX_CHARS = 80


def _looks_like_heading(text: str) -> bool:
    stripped = (text or "").strip()
    # A table row ("CAP | 12 months of fees") or a short line stating a quantity
    # ("Cure period: 30 days") is a position, not a heading — AM-54's live corpus
    # showed the guard swallowing both and minting evidence-free MISSINGs. Only
    # the section number itself may carry digits ("3. Limitation of Liability").
    body = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", stripped)
    return ("\n" not in stripped and len(stripped) < _HEADING_MAX_CHARS
            and not stripped.endswith((".", ";", ")"))
            and "|" not in body and not re.search(r"\d", body))


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
    # Terminology marking a MULTI-LIMB formula ("greater of", "whichever is
    # less"). A clause stating one is never reduced to whichever limb happens to
    # be readable: reading a limb that equals the Standard would produce a false
    # MATCH — silent acceptance of a formula nobody compared (ENG-09, 45B.4).
    # A match forces UNKNOWN, so the whole formula goes to a human as evidence.
    composite_phrases: tuple[str, ...] = ()
    # 44.30 "regex/pattern matching for structured values" — the unit names that may
    # follow a magnitude. Configured, so no unit vocabulary is assumed.
    #
    # Two shapes are accepted, mirroring ``bases``:
    #   tuple  — each matched term is recorded verbatim as ``cap_unit``;
    #   dict   — canonical unit key -> the terms that denote it. The matched term
    #            is recorded as its canonical key, so a Company Standard declaring
    #            ``unit: "DAYS"`` can be met by clause text reading "calendar days"
    #            or "consecutive days" WITHOUT the evaluator comparing units it was
    #            never told are the same (45C.23 stands: the equivalence is
    #            configured terminology, never assumed by code).
    units: tuple[str, ...] | dict[str, tuple[str, ...]] = ()
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
        raw_units = block.get("units") or ()
        units: tuple[str, ...] | dict[str, tuple[str, ...]]
        if isinstance(raw_units, dict):
            units = {k: tuple(v) for k, v in raw_units.items()}
        else:
            units = tuple(raw_units)
        return cls(
            cap_phrases=tuple(block.get("cap_phrases") or ()),
            unlimited_phrases=tuple(block.get("unlimited_phrases") or ()),
            composite_phrases=tuple(block.get("composite_phrases") or ()),
            units=units,
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
        caps=prune_absent(caps),
        extraction_status=status,
        extraction_diagnostics=tuple(diagnostics),
    )


def prune_absent(caps: list[Cap]) -> tuple[Cap, ...]:
    """An ABSENT cap says "this clause states nothing"; it is not a position.
    Beside a clause of the same kind and scope that DOES state one, it is dropped
    — otherwise a mapped exclusions clause would turn a clean cap into a
    same-scope CONFLICT (45C.2 is about incompatible POSITIONS). Alone, ABSENT
    stands, with its evidence (AM-52)."""
    stated = {(c.cap_kind, c.scope, c.scope_label) for c in caps if c.cap_status != ABSENT}
    return tuple(c for c in caps
                 if c.cap_status != ABSENT or (c.cap_kind, c.scope, c.scope_label) not in stated)


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
        # The mapping layer already confirmed this clause is relevant to THIS
        # Requirement (`confirmed_clauses` — 35.x's own confirm_threshold), so
        # a mapped clause stating neither a cap nor unlimited-liability phrase
        # is an established ABSENCE, not a missing observation: rule 11 requires
        # every Finding to trace to its evidence, and 45C.14's own worked
        # example (a damages-exclusion clause with no monetary cap) requires
        # exactly this — "the clause was found and mapped, so it must remain
        # attached" — MISSING, but never with the supporting text discarded.
        # No new phrase is added and no clause is reclassified: this only
        # keeps the clause the mapping layer already confirmed as its evidence.
        #
        # EXCEPT a bare heading fragment ("1. Limitation of Liability" with no
        # body) — `section_heading_terms` lets mapping confirm a heading on its
        # own, and a heading is not a legal position to attach as evidence of
        # absence. `_looks_like_heading` mirrors the same narrow, deliberate
        # judgment `assist/chunking.py::_is_heading` already makes (a separate
        # copy, not an import: the authoritative path does not depend on the
        # assist lane, AM-25 r2) — one line, short, not a sentence.
        if _looks_like_heading(clause.content):
            return []
        return [Cap(cap_kind=EvaluationKind.PRIMARY, scope=config.general_scope,
                    scope_label=None, cap_status=ABSENT, cap_value=None,
                    cap_unit=None, cap_basis=None, evidence_refs=evidence)]

    states_composite = any(
        contains_phrase(body, phrase) for phrase in config.composite_phrases)
    magnitude = (_find_magnitude(body, config.units)
                 if not (states_unlimited or states_composite) else None)
    basis = _find_basis(body, config.bases)

    if states_unlimited:
        status, value, unit = UNLIMITED, None, None
    elif states_composite:
        # A multi-limb formula is never reduced to one readable limb — a limb
        # equal to the Standard would otherwise MATCH silently. UNKNOWN sends
        # the whole formula to a human with the clause as evidence.
        status, value, unit = UNKNOWN, None, None
        diagnostics.append(
            f"clause {_label(clause)} states a multi-limb cap formula "
            "(configured composite terminology matched); no single limb is "
            "read as the cap")
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


def _find_magnitude(
    body: str,
    units: tuple[str, ...] | dict[str, tuple[str, ...]],
) -> tuple[float, str] | None:
    """Locked 44.30 "regex/pattern matching for structured values".

    Recognises a number immediately followed by one of the **configured** units. No
    unit vocabulary is built in. Since AM-54 (owner, 2026-09-09) a number WORD
    ("six", "twenty-four") is read as the numeral it is — a numeral is not legal
    terminology, so 35.4/44.29 are untouched; what is still never done is GUESSING
    a number the text does not state (44.24).

    Legal drafting states magnitudes as ``twelve (12) months`` — the word, then the
    digits in parentheses, then the unit — or mirrored as ``15 (fifteen) calendar
    days``. The digits ARE stated in both, so reading them is pattern mechanics,
    not word-number interpretation: an optional closing parenthesis, or one
    parenthesised word, may sit between the number and its unit. ``six months``
    with no digits remains unrecognisable, deliberately — and a clause matching a
    configured composite phrase never reaches this function at all.

    When ``units`` is a dict the matched term is reported as its canonical key (see
    ``LiabilityExtractionConfig.units``); terms are tried longest-first so a
    configured ``consecutive days`` wins over a configured ``days`` at the same
    position, and ties are broken alphabetically so the result is deterministic
    (`ENG-11`).

    Returns the FIRST match in document order so the result is deterministic when a
    clause states several magnitudes; a clause with more than one is reported as a
    diagnostic by the caller only if none matched at all.
    """
    if isinstance(units, dict):
        pairs = [(normalize(term), canonical)
                 for canonical in units for term in units[canonical]]
    else:
        pairs = [(normalize(term), term) for term in units]
    canonical_for: dict[str, str] = {}
    for term, canonical in sorted(pairs, key=lambda p: (-len(p[0]), p[0], p[1])):
        if term and term not in canonical_for:
            canonical_for[term] = canonical
    if not canonical_for:
        return None
    alternatives = "|".join(re.escape(t) for t in canonical_for)
    # Digits with optional thousands separators and decimals, then the unit. The
    # optional `\)` is the "twelve (12) months" convention; the optional
    # parenthesised word is its mirror, "15 (fifteen) calendar days".
    # AM-54 (owner, 2026-09-09): a number WORD is a numeral, not terminology —
    # "six months" and "6 months" state the same quantity, and reading the word
    # is arithmetic, not a synonym the engine invented (35.4 governs legal
    # terminology, which a numeral is not). Words to ninety-nine; "twenty-four"
    # and "twenty four" both read.
    pattern = re.compile(
        rf"(?<!\w)(\d{{1,3}}(?:,\d{{3}})*(?:\.\d+)?|\d+(?:\.\d+)?|{_NUMBER_WORD})\s*"
        rf"(?:\)|\([a-z0-9]+\))?\s*"
        rf"({alternatives})(?!\w)")
    match = pattern.search(body)
    if match is None:
        return None
    value = parse_number(match.group(1))
    if value is None:                                   # pragma: no cover
        return None
    return value, canonical_for[match.group(2)]


_UNITS_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
                "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
                "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
_TENS_WORDS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
               "seventy": 70, "eighty": 80, "ninety": 90}
_NUMBER_WORD = (r"(?:(?:" + "|".join(_TENS_WORDS) + r")(?:[- ](?:" + "|".join(
    k for k, v in _UNITS_WORDS.items() if v < 10) + r"))?|" + "|".join(_UNITS_WORDS) + r")")


def parse_number(token: str) -> float | None:
    """Digits (with separators) or a number word up to ninety-nine, as a float."""
    raw = token.strip().lower().replace(",", "")
    try:
        return float(raw)
    except ValueError:
        pass
    parts = re.split(r"[- ]", raw)
    if len(parts) == 1 and raw in _UNITS_WORDS:
        return float(_UNITS_WORDS[raw])
    if len(parts) == 1 and raw in _TENS_WORDS:
        return float(_TENS_WORDS[raw])
    if len(parts) == 2 and parts[0] in _TENS_WORDS and parts[1] in _UNITS_WORDS \
            and _UNITS_WORDS[parts[1]] < 10:
        return float(_TENS_WORDS[parts[0]] + _UNITS_WORDS[parts[1]])
    return None


def number_in_text(value: float, body: str) -> bool:
    """Whether ``value`` is WRITTEN in ``body`` — as digits or as a number word.
    The mechanical check behind every semantically read magnitude (AM-54)."""
    for token in re.findall(rf"\d+(?:\.\d+)?|{_NUMBER_WORD}", body):
        if parse_number(token) == value:
            return True
    return False


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

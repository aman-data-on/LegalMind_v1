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
from dataclasses import dataclass, field, replace

from legalmind.domain.enums import EvaluationKind, ExtractionStatus
from legalmind.evaluation.contracts import Cap, LiabilityFacts
from legalmind.mapping.engine import Clause
from legalmind.mapping.scoring import contains_phrase, normalize, phrase_pattern

# cap_status values — locked 45A §4 / 45B.4. Mirrored from numeric.py rather than
# imported to keep the extractor independent of the evaluator; both cite the lock.
FINITE = "FINITE"
UNLIMITED = "UNLIMITED"
ABSENT = "ABSENT"
UNKNOWN = "UNKNOWN"
#: `AM-154` (owner, 2026-10-16): "Do NOT allow the system to treat working days as
#: calendar days." A period the clause states in working or business days is never
#: compared with a calendar-day standard: it is its own status, which the evaluator
#: reports as a DEVIATION for a person.
WORKING_DAYS = "WORKING_DAYS"
_WORKING_TERMS = ("working days", "working day", "business days", "business day")
#: Any stated period, read or not ("three (3) weeks" beside a DAYS standard): a clause
#: about the term stating one is found, its figure unread — never "not in the contract".
#: Not "consecutive days": that is how long an event lasts (force majeure), no term.
_PERIOD_FIGURE = re.compile(
    r"(?<![\w.])\d+(?:\.\d+)?\s*\)?\s*(?:(?:business|working)\s+)?"
    r"(?:days?|weeks?|months?|years?)(?!\w)", re.I)


def _with_working_days(units):
    """A DAYS standard's units with working/business days split out as their own unit
    (`AM-154`): (calendar units, calendar + WORKING_DAYS). Other units unchanged."""
    if isinstance(units, dict) and "DAYS" in units:
        calendar = {k: tuple(t for t in v if normalize(t) not in _WORKING_TERMS)
                    for k, v in units.items()}
        return calendar, {**calendar, WORKING_DAYS: _WORKING_TERMS}
    return units, units

# The reserved scope key for a general cap. 45C uses per-Requirement scope
# vocabulary (AM-8'), and this is the one value the extractor may supply itself
# because it names "the general rule" rather than any legal category.
SCOPE_GENERAL = "GENERAL"

# A bare heading is not a clause — mirrors `assist/ingestion/chunking.py::_is_heading`'s
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
    # AM-164 — words one of which must stand in the SENTENCE that holds a cap phrase, for
    # it to be a cap at all ("will not exceed the full monthly amount" in a service-credit
    # clause, "shall not exceed 4 hours" in a maintenance clause: no liability word, so no
    # cap). Empty = no such check (the numeric standards that are not caps).
    cap_context_terms: tuple[str, ...] = ()
    #: The standard's own topic words (its mapping vocabulary — aliases, exact phrases,
    #: keyword-group words): a period read through its basis words must sit in a
    #: sentence that also names the topic, so "support … for 2 years afterwards" under a
    #: Confidentiality heading is never the confidentiality survival (2026-10-23). Empty:
    #: no such requirement (the phrase-read path never needs it).
    topic_terms: tuple[str, ...] = ()
    #: AM-198 — words naming ANOTHER position the Constitution states separately ("trade
    #: secret": §15's own carve-out). A sentence naming one never states this one: "such
    #: obligations shall continue for so long as … a trade secret" is no second period.
    other_positions: tuple[str, ...] = ()

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
            cap_context_terms=tuple(block.get("cap_context_terms") or ()),
            other_positions=tuple(block.get("other_positions") or ()),
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
        body = normalize(bullets_end_sentences(clause.content))
        if not body:
            unread_clauses += 1
            diagnostics.append(f"clause {_label(clause)} has no readable text")
            continue
        if config.other_positions:
            body = " ".join(
                s for s in re.split(r"(?<=[.;])\s+", body)
                if not any(contains_phrase(s, t) for t in config.other_positions))
            if not body:
                diagnostics.append(
                    f"clause {_label(clause)} states another position only")
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


def _cap_in_context(body: str, config: LiabilityExtractionConfig) -> bool:
    """A cap phrase counts only in a sentence that is about liability (AM-164): one of
    the configured context words stands in the sentence that holds a cap phrase."""
    for sentence in re.split(r"(?<=[.;])\s+", body):
        if any(contains_phrase(sentence, p) for p in config.cap_phrases) and any(
                contains_phrase(sentence, t) for t in config.cap_context_terms):
            return True
    return False


#: AM-164 — a sentence that takes a breach-wide class of claims OUT of the limitation
#: ("The limitation in clause 5.1 shall not apply to any breach of this Agreement by
#: LeapSwitch"): the cap is then no cap for the claims it exists for. Only a sentence that
#: names the limitation and a breach-wide class is one; a named carve-out (death, fraud,
#: a liability the law does not allow to be excluded) is not.
_DISAPPLIES = re.compile(
    r"\b(?:limitation|limit|cap|clause\s+\d[\d.]*|section\s+\d[\d.]*)\b[^.;]{0,80}?"
    r"\b(?:shall|will|does|do)\s+not\s+(?:apply|extend)\s+(?:to|in respect of)\s+"
    r"(?:any|all)\s+(?:and all\s+)?(?:"
    r"breach(?:es)?\s+of\s+(?:this|the)\s+(?:agreement|contract)|"
    r"breach(?:es)?\s+by\s+\w+|breach(?:es)?\s*(?:[.;,]|$)|"
    r"(?:claims?|liabilit(?:y|ies)|losses|defaults?)\s*"
    r"(?:[.;,]|$|(?:under|arising\s+(?:out of|under))\s+this\s+agreement))")
_PROTECTED_CLASS = re.compile(
    r"\b(?:fraud|wilful|willful|gross negligence|death|personal injury|bodily|"
    r"cannot be (?:excluded|limited)|by law|intellectual property|confidential)", re.I)


def cap_disapplied(clauses: list[Clause]) -> tuple[Clause, ...]:
    """The clauses of the document that disapply the limitation to a breach-wide class of
    claims (AM-164). Read over every clause: the disapplying sentence need not be in the
    clause that states the cap."""
    found = []
    for clause in clauses:
        for sentence in re.split(r"(?<=[.;])\s+", normalize(clause.content or "")):
            if _DISAPPLIES.search(sentence) and not _PROTECTED_CLASS.search(sentence):
                found.append(clause)
                break
    return tuple(found)


#: AM-195 (2026-10-26, amends AM-164's protected list): Constitution §9 (L1.14) — "No
#: separate multiplier or super-cap has been approved ... for confidentiality, IP
#: infringement, data-breach, privacy, cybersecurity, or other exceptional claims". A
#: sentence that takes one of THOSE classes out of the cap leaves it uncapped there; what
#: the law will not let anyone limit (fraud, death, personal injury) stays protected.
_SECTION_9_CLASSES = re.compile(
    r"\b(?:confidential\w*|data\s+(?:protection|breach|security|privacy)|privacy|"
    r"cyber\s*security|security\s+(?:breach|incident)|intellectual\s+property|"
    r"infringe\w*|indemnif\w*|indemnit\w*)", re.I)
_CAP_NOT_FOR = re.compile(
    r"\b(?:cap|limitation|limit)\b.{0,80}?\b(?:shall|will|does|do)\s+not\s+"
    r"(?:apply|extend)\s+(?:to|in\s+respect\s+of)\b(?P<rest>.*)"
    r"|(?P<head>.*)\b(?:shall|will)\s+not\s+be\s+subject\s+to\s+(?:the|any)\s+"
    r"(?:cap|limitation)", re.I)


def cap_carved_out(clauses: list[Clause]) -> tuple[tuple[Clause, str], ...]:
    """The clauses that take a §9-named class of claims out of the cap, with the class
    named (AM-195). Read over every clause, as `cap_disapplied` is."""
    found = []
    for clause in clauses:
        text = " ".join((clause.content or "").split())
        for sentence in re.split(r"(?<=\.)\s+", text):   # "9.1" never splits
            m = _CAP_NOT_FOR.search(sentence)
            said = (m.group("rest") or m.group("head") or "") if m else ""
            hit = _SECTION_9_CLASSES.search(said)
            if hit:
                found.append((clause, hit.group(0)))
                break
    return tuple(found)


def prune_absent(caps: list[Cap]) -> tuple[Cap, ...]:
    """An ABSENT cap says "this clause states nothing"; it is not a position.
    Beside a clause of the same kind and scope that DOES state one, it is dropped
    — otherwise a mapped exclusions clause would turn a clean cap into a
    same-scope CONFLICT (45C.2 is about incompatible POSITIONS). Alone, ABSENT
    stands, with its evidence (AM-52)."""
    stated = {(c.cap_kind, c.scope, c.scope_label)
              for c in caps if c.cap_status != ABSENT}
    return _restated_once([c for c in caps
                           if c.cap_status != ABSENT
                           or (c.cap_kind, c.scope, c.scope_label) not in stated])


#: Most specific first: what a person most needs to hear about an unread term.
_SPECIFIC = {r: i for i, r in enumerate((
    "PLACEHOLDER", "NEGATED", "QUALIFIED", "FIGURE_NOT_READ", "SEVERAL_FIGURES",
    "MODEL_UNVERIFIED",
    "NO_FIGURE_STATED", "PAID_IN_ADVANCE", "APPLICABILITY_UNCERTAIN"))}


def one_position(caps) -> tuple[Cap, ...]:
    """`_restated_once` for callers outside extraction (after the semantic reading)."""
    return _restated_once(list(caps))


def _restated_once(caps: list[Cap]) -> tuple[Cap, ...]:
    """The same cap stated twice ("6 months of fees" in clause 10.1 and again in an
    annexure) is ONE position, not a CONFLICT (45C.2 is about incompatible positions):
    same kind, scope, figure and unit, and a basis or party that one states and the other
    leaves unsaid (never two different ones). Kept once, citing every clause that
    states it (2026-10-23)."""
    out: list[Cap] = []
    for cap in caps:
        if cap.cap_status == UNKNOWN:
            # several unread readings of one term are ONE: the most specific reason
            # speaks ("§7.1 leaves the figure blank" over "may not apply"), every
            # clause stays cited (2026-10-23)
            at = next((i for i, kept in enumerate(out) if kept.cap_status == UNKNOWN
                       and (kept.cap_kind, kept.scope, kept.scope_label)
                       == (cap.cap_kind, cap.scope, cap.scope_label)), None)
            if at is not None:
                kept = out[at]
                lead, other = sorted((kept, cap), key=lambda c: _SPECIFIC.get(
                    c.reason or "", len(_SPECIFIC)))
                out[at] = replace(lead, evidence_refs=tuple(dict.fromkeys(
                    kept.evidence_refs + cap.evidence_refs)),
                    candidates=tuple(dict.fromkeys(lead.candidates + other.candidates)))
                continue
        same = next((i for i, kept in enumerate(out)
                     if cap.cap_status == kept.cap_status == FINITE
                     and (cap.cap_kind, cap.scope, cap.scope_label, cap.cap_value,
                          cap.cap_unit) == (kept.cap_kind, kept.scope, kept.scope_label,
                                            kept.cap_value, kept.cap_unit)
                     and (cap.cap_basis is None or kept.cap_basis is None
                          or cap.cap_basis == kept.cap_basis)
                     and (cap.cap_party is None or kept.cap_party is None
                          or cap.cap_party == kept.cap_party)), None)
        if same is None:
            out.append(cap)
            continue
        kept = out[same]
        out[same] = replace(kept, cap_basis=kept.cap_basis or cap.cap_basis,
                            cap_party=kept.cap_party or cap.cap_party,
                            evidence_refs=tuple(dict.fromkeys(
                                kept.evidence_refs + cap.evidence_refs)))
    return tuple(out)


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
    if states_cap and config.cap_context_terms and not _cap_in_context(body, config):
        states_cap = False                  # "will not exceed" about credits, hours …
    # A clause the mapping confirmed, in words no cap phrase names ("remedy it within 30
    # days", "for 3 years afterwards"), is read at the standard's own basis words — the
    # same sentence, the same blank and several-figure guards (2026-10-23). A standard
    # with a guarded cap context (liability) is read only through its cap phrases.
    # Periods only (notice, cure, survival, payment days): a cap that can be unlimited
    # or is guarded by context (liability) is never read past its cap words — "shall
    # exceed the fees paid in 12 months" is not a 12-month cap. And only where the
    # sentence states a figure or leaves one blank: nothing to read is not a reading.
    anchors = config.cap_phrases
    hit: str | None = None
    if not (states_unlimited or states_cap or config.cap_context_terms
            or config.unlimited_phrases):
        by_basis = tuple(t for terms in config.bases.values() for t in terms)
        # the FIRST sentence that names the basis AND states a figure or a blank: "The
        # first invoice is payable before activation. … received at least [7] days
        # before that date." reads the second (the real PO, 22 Oct)
        # a NOTICE period is stated with "notice": "consecutive rolling 90 days terms"
        # is a renewal period, never a non-renewal notice (CtrlS §1.23, 2026-10-23)
        notice = any("NOTICE" in code for code in config.bases)
        # working days too (QA-018): "billing disputes … within 15 business days" is the
        # dispute window, as working days — but only where the sentence names the topic
        # beyond its basis word ("errors … within 5 working days of the Invoice" is no
        # payment period: MSA 8.10)
        with_working = _with_working_days(config.units)[1]
        hit = next((s for s in re.split(r"(?<=[.;])\s+", body)
                    if _phrase_span(s, by_basis) is not None
                    and (not notice or _phrase_span(s, ("notice",)) is not None)
                    and (not config.topic_terms
                         or _phrase_span(s, config.topic_terms) is not None)
                    # a FIGURE is read only beside a topic word that is not the basis
                    # word itself: "10 days prior to the date of invoice" is a GST
                    # notice, no payment period (MSA 8.6, 2026-10-30) — the QA-018
                    # rule, for calendar days too. A blank is never compared, so it
                    # keeps the wider reading (PLACEHOLDER, a person reads it).
                    and ((_find_magnitude(s, with_working if _beyond_basis(s, config)
                                          else config.units) is not None
                          and _names_topic(s, config))
                         or _blank_in(s))),
                   None)
        if hit is not None:
            states_cap, anchors = True, tuple(
                t for t in by_basis if _phrase_span(hit, (t,)) is not None)
            diagnostics.append(f"clause {_label(clause)}: read at its basis words — no "
                               "configured cap phrase states this term")

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
        # judgment `assist/ingestion/chunking.py::_is_heading` already makes (a separate
        # copy, not an import: the authoritative path does not depend on the
        # assist lane, AM-25 r2) — one line, short, not a sentence.
        if _looks_like_heading(clause.content):
            return []
        # AM-156 — "within [30 days] of the invoice date": the bracket splits the cap
        # phrase. Read without brackets it states the cap, so it is a placeholder, not
        # an established absence.
        unbracketed = re.sub(r"\\?[\[\]]", "", body)
        if unbracketed != body and _blank_in(body) and any(
                contains_phrase(unbracketed, phrase) for phrase in config.cap_phrases):
            diagnostics.append(f"clause {_label(clause)} leaves the figure blank or in "
                               "brackets: not agreed, not compared")
            return [Cap(cap_kind=EvaluationKind.PRIMARY, scope=config.general_scope,
                        scope_label=None, cap_status=UNKNOWN, cap_value=None,
                        cap_unit=None, cap_basis=None, evidence_refs=evidence,
                        reason=PLACEHOLDER)]
        # A figure in the standard's own units that nothing read is not an absence: the
        # clause is found, its figure unconfirmed — for a person, citing it (rule 15).
        if _about_this_term(body, config):
            diagnostics.append(f"clause {_label(clause)} states a figure in this "
                               "term's units that no configured wording reads")
            return [Cap(cap_kind=EvaluationKind.PRIMARY, scope=config.general_scope,
                        scope_label=None, cap_status=UNKNOWN, cap_value=None,
                        cap_unit=None, cap_basis=_find_basis(body, config.bases),
                        evidence_refs=evidence, reason=FIGURE_NOT_READ,
                        candidates=stated_figures(clause.content))]
        return [Cap(cap_kind=EvaluationKind.PRIMARY, scope=config.general_scope,
                    scope_label=None, cap_status=ABSENT, cap_value=None,
                    cap_unit=None, cap_basis=None, evidence_refs=evidence)]

    states_composite = any(
        contains_phrase(body, phrase) for phrase in config.composite_phrases)
    # AM-62 r5 — the quantity the cap phrase INTRODUCES: a clause stating
    # several periods ("due within 21 days … disputes within 15 days … 30 days'
    # notice") is read at the number nearest its first cap phrase, not at its
    # first number. Every candidate is still a number the clause states (44.24).
    anchor = _phrase_span(body, anchors)
    if hit is not None and (where := body.find(hit)) >= 0:
        local = _phrase_span(hit, anchors)        # the basis word IN the found sentence
        anchor = (where + local[0], where + local[1]) if local else anchor
    # AM-154 r2 / AM-155: a standard measured in DAYS also reads "N working/business
    # days" — as its own unit, never as calendar days — but only in the sentence its
    # cap phrase introduces ("acknowledge within 5 business days" beside a one-month
    # cure period is not the cure period). Standards in months or years never do.
    # Working days are split out whenever a standard is in days — never read as
    # calendar days, with or without an anchor (a phrase matched only in an inflected
    # form has none): unanchored, a working-day figure stays a working-day figure,
    # for a person. One in ANOTHER sentence than the cap phrase is read past, and the
    # clause's other figures are read without it (review of AM-155, 2026-10-17).
    calendar, units = _with_working_days(config.units)
    magnitude = (_find_magnitude(body, units, anchor=anchor)
                 if not (states_unlimited or states_composite) else None)
    if magnitude is not None and magnitude[1] == WORKING_DAYS and anchor is not None \
            and not _same_sentence(body, anchor, magnitude[2]):
        magnitude = _find_magnitude(body, calendar, anchor=anchor)
    basis = _find_basis(body, config.bases)
    if config.composite_phrases and magnitude is not None and anchor is not None \
            and _states_second_figure(body, anchor, magnitude[2]):
        # A standard that declares multi-limb formulas a risk (composite_phrases)
        # also fails closed on one its phrases did not name: a currency limb or a
        # second quantity beside the cap ("the lower of INR 50,000 and …",
        # "INR 10,00,000 or …") is never read as its one readable limb (A2).
        states_composite, magnitude = True, None
    is_qualified = False
    if config.cap_context_terms and magnitude is not None and anchor is not None:
        # QA-002 (2026-10-29): a cap sentence that averages, multiplies or moves the
        # window states another formula than the figure read; a carve-back in it or
        # the next sentence makes the cap one-sided. Grammar, not a position — it
        # sends the cap to a person, like a second limb.
        start = _sentence_start(body, anchor[0])
        stop = _sentence_stop(body, max(anchor[1], magnitude[2][1]))
        if qualified(body[start:stop], body[start:_sentence_stop(body, stop)]):
            is_qualified, magnitude = True, None

    reason: str | None = None
    beside: tuple | None = None
    # AM-156 — a figure the parties have not agreed is never a term to compare. In the
    # cap phrase's own sentence: a blank ("_____ months") or a bracketed figure ("[30]
    # days", "[up to 12 months]") makes it a placeholder — even when another sentence
    # states a figure (that figure is not this term: rule 15), and when the read figure
    # sits inside an open bracket.
    placeholder = False
    if anchor is not None:
        start = _sentence_start(body, anchor[0])
        sentence = body[start:_sentence_stop(body, anchor[1])]
        enclosed = magnitude is not None and _in_bracket(body, start, magnitude[2][0])
        placeholder = enclosed or (_blank_in(sentence) and (
            magnitude is None or not _same_sentence(body, anchor, magnitude[2])))
    if placeholder:
        magnitude = None
    # A period the sentence negates or excuses ("No party is obliged to remedy it within
    # 30 days where …", "is not required to give 30 days' notice") is no period: for a
    # person, never compared. Periods only — a cap's own wording is "shall not exceed".
    negated = False
    if (anchor is not None and magnitude is not None and not config.unlimited_phrases
            and not config.cap_context_terms):
        start = _sentence_start(body, anchor[0])
        negated = _NEGATED.search(body[start:anchor[1]]) is not None
    if negated:
        magnitude = None
    if states_unlimited:
        status, value, unit = UNLIMITED, None, None
        beside = _find_magnitude(body, units, anchor=anchor)
        if beside is not None:
            # QA-054: "fees for twelve months … gross negligence is not capped" is still
            # UNLIMITED for a person to weigh (which carve-out is acceptable is a Legal
            # Rule, rule 7) — but the reader is told the clause also states a figure
            reason = BESIDE_A_FIGURE
    elif is_qualified:
        status, value, unit = UNKNOWN, None, None
        reason = QUALIFIED
        diagnostics.append(f"clause {_label(clause)} averages, multiplies, re-windows or "
                           "carves back its cap figure: not compared")
    elif states_composite:
        # A multi-limb formula is never reduced to one readable limb — a limb
        # equal to the Standard would otherwise MATCH silently. UNKNOWN sends
        # the whole formula to a human with the clause as evidence.
        status, value, unit = UNKNOWN, None, None
        reason = SEVERAL_FIGURES
        diagnostics.append(
            f"clause {_label(clause)} states a multi-limb cap formula "
            "(configured composite terminology, or a second figure beside the "
            "cap); no single limb is read as the cap")
    elif negated:
        status, value, unit = UNKNOWN, None, None
        reason = NEGATED
        diagnostics.append(f"clause {_label(clause)} negates or excuses the period it "
                           "states: not compared")
    elif placeholder:
        status, value, unit = UNKNOWN, None, None
        reason = PLACEHOLDER
        diagnostics.append(f"clause {_label(clause)} leaves the figure blank or in "
                           "brackets: not agreed, not compared")
    elif magnitude is not None and magnitude[1] == WORKING_DAYS:
        status, value, unit = WORKING_DAYS, magnitude[0], WORKING_DAYS
    elif magnitude is not None:
        status, value, unit = FINITE, magnitude[0], magnitude[1]
    else:
        # Cap language without a recognisable magnitude. Locked 44.24: uncertainty
        # is recorded deterministically, never resolved into a number.
        status, value, unit = UNKNOWN, None, None
        reason = FIGURE_NOT_READ if stated_figures(clause.content) else NO_FIGURE_STATED
        diagnostics.append(
            f"clause {_label(clause)} states a liability cap but no magnitude was "
            "recognised in the configured units")
    candidates = stated_figures(clause.content) if reason else ()
    if reason == BESIDE_A_FIGURE and not candidates and beside is not None:
        candidates = (f"{beside[0]:g} {beside[1].lower()}",)   # the figure as read

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
            reason=reason,
            candidates=candidates,
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
            reason=reason,
            candidates=candidates,
        ))

    return results


#: Why an UNKNOWN cap was not read — the reader's sentence, never a result (2026-10-16).
NO_FIGURE_STATED = "NO_FIGURE_STATED"      # the clause states no figure at all
FIGURE_NOT_READ = "FIGURE_NOT_READ"        # it states figures; none read as this term
SEVERAL_FIGURES = "SEVERAL_FIGURES"        # a formula of several limbs or figures
QUALIFIED = "QUALIFIED"        # QA-002: averaged, multiplied, re-windowed or carved back
BESIDE_A_FIGURE = "BESIDE_A_FIGURE"   # QA-054: unlimited wording beside a stated cap
MODEL_UNVERIFIED = "MODEL_UNVERIFIED"      # a figure the model named, not in the words
APPLICABILITY_UNCERTAIN = "APPLICABILITY_UNCERTAIN"  # another type's standard, no figure
PLACEHOLDER = "PLACEHOLDER"                # "[30] days", "_____ months": not yet agreed
NEGATED = "NEGATED"                        # "no party is obliged to remedy it …"
PAID_IN_ADVANCE = "PAID_IN_ADVANCE"        # prepaid: no invoice period to compare

#: An obligation the sentence takes away before the period it names.
#: QA-002 — a cap's figure averaged, multiplied or counted over another window.
_QUALIFIED = re.compile(
    r"\b(?:average|(?<!all )times|multiplied|twice|double|treble|triple|per\s+cent|"
    r"percent|per\s+month)\b|\d\s*(?:%|x\b)|"
    r"\b(?:months?|years?)\s+(?:immediately\s+)?(?:following|after|from|succeeding|"
    r"subsequent)\b|\bfirst\s+(?:\w+\s+)?(?:\(\d+\)\s+)?(?:months?|years?)\b", re.I)
#: QA-002 — a party carved back out of the cap, or the figure left to one side.
_CARVED_BACK = re.compile(
    r"\bremains?\s+(?:fully\s+)?liable\b|\bin\s+excess\s+(?:thereof|of\s+(?:that|such|the\s+cap))|"
    r"\bwaives?\s+(?:the\s+)?benefit\b|\bsuch\s+other\s+(?:amount|sum)\b|"
    r"\b(?:except|other\s+than)\s+(?:for\s+)?(?:the\s+)?(?:customer|client|you|licensee|"
    r"leapswitch|cloudpe|provider|supplier|vendor|company|partner)\b(?!['\u2019]s)", re.I)


def qualified(sentence: str, with_next: str | None = None) -> bool:
    """QA-002: the cap's figure is averaged, multiplied or re-windowed in ``sentence``,
    or a party is carved back out of it there or in the next sentence."""
    return bool(_QUALIFIED.search(sentence) or _CARVED_BACK.search(with_next or sentence))


_NEGATED = re.compile(r"\b(?:no\s+party|neither\s+party|not|never|no\s+obligation)\b"
                      r"[^.;]{0,40}?\b(?:obliged|obligated|required|bound|need|have\s+to|"
                      r"to)\b", re.I)
#: A blank, plain or Markdown-escaped ("_____", "\\_\\_\\_").
_UNDERSCORES = re.compile(r"(?:\\?_){3,}")
_BRACKET = re.compile(r"\\?\[([^\]\n]{0,80}?)\\?\]")
#: A drafting instruction left in brackets: "[insert]", "[TBD]", "[to be agreed]".
_INSTRUCTION = re.compile(r"(?:insert|tbd|tbc|to\s+be\s+(?:agreed|confirmed|decided|"
                          r"inserted)|number|no\.?)\b[^\]]*", re.I)
_NOT_A_FIGURE = re.compile(r"\s*(?:clause|section|schedule|annex\w*|appendix|exhibit|"
                           r"article|para\w*|sub-?clause)\b", re.I)
_UNIT_AFTER = re.compile(r"\s*(?:days?|weeks?|months?|years?|%|per\s*cent|percent)(?!\w)",
                         re.I)
#: A sentence ends at "." or ";" — but not after an abbreviation ("Rs. 5,000").
#: A bullet opening a line ("– Liability capped at …", "• …", "● …", "▪ …", "* …"),
#: or a numbered item "(a)"/"a)"/"i." — it ends the sentence before it, as a full stop
#: would: an annexure of bulleted terms without full stops is several sentences, never
#: one sentence holding "3 years" and "6 months" (the real PO, 23 Oct; AM-152 r5 did the
#: same for money terms).
_LINE_BULLET = re.compile(r"\n[ \t]*(?:[\u2013\u2014\-\u2022\u25cf\u25aa*]|\(?[a-z]\)|"
                          r"\(?[ivx]{1,4}\)|\d{1,2}\))\s")


#: A running header or footer line ("TSIN – LeapSwitch PO | Page 6 of 9", "Page 3/12"):
#: it states no term, and a "6 of 9" beside "6 months" is no second figure.
_PAGE_LINE = re.compile(r"(?im)^(?:[^\n]*\bpage\s+\d+\s*(?:of|/)\s*\d+\b[^\n]*"
                        r"|[ \t]*page\s+\d+[ \t]*|[ \t]*-[ \t]*\d+[ \t]*-[ \t]*"
                        r"|[ \t]*\d+[ \t]*\|[^\n\d]{0,40}"
                        r"|[^\n\d]{0,40}\|[ \t]*\d+[ \t]*)$")


def bullets_end_sentences(text: str | None) -> str:
    """The clause's text as it is READ (never as it is quoted): a running page header or
    footer line dropped, and each line-opening bullet read as a sentence end."""
    text = _PAGE_LINE.sub(";", text or "")
    return _LINE_BULLET.sub(lambda m: ";" + m.group(0), text)


_STOP = re.compile(r"(?<!\brs)(?<!\bno)(?<!\bcl)(?<!\binr)[.;](?:\s|$)", re.I)


def _blank_in(text: str) -> bool:
    """Whether ``text`` leaves a figure blank or in brackets — "_____", "[30] days",
    "[●]", "[up to 12 months]" — never a cross-reference ("[Clause 17.4]"), a footnote
    ("[1]"), a Markdown link ("[Schedule 2](…)") or a word repeating a stated number
    ("01 [ONE] Year")."""
    if _UNDERSCORES.search(text):
        return True
    for m in _BRACKET.finditer(text):
        inner = m.group(1).strip()
        if text[m.end():m.end() + 1] == "(" or _NOT_A_FIGURE.match(inner):
            continue
        if re.search(r"[\d)]\s*\\?$", text[:m.start()]):
            continue                                  # a repeat of the number before it
        fill = (re.fullmatch(r"[●•*x_.\-\s]*", inner) is not None
                or _INSTRUCTION.fullmatch(inner) is not None)
        bare = re.fullmatch(r"[\d.,]+", inner) is not None
        if fill or (bare and _UNIT_AFTER.match(text[m.end():])) or (
                not bare and (re.search(r"\d", inner)
                              or re.search(rf"\b{_NUMBER_WORD}\b", inner, re.I))):
            return True
    return False


def _in_bracket(body: str, start: int, at: int) -> bool:
    """Whether position ``at`` sits inside a bracket opened after ``start``."""
    opened = body.rfind("[", start, at)
    return opened >= 0 and "]" not in body[opened:at]

_FIGURE = re.compile(
    r"(?<![\w.])\d+(?:[.,]\d+)*\s*(?:\([a-z -]+\)\s*)?-?\s*"
    r"(?:(?:consecutive|calendar|business|working|clear)\s+)?"
    r"(?:days?|weeks?|months?|years?|hours?|minutes?|per\s*cent|percent|%)(?!\w)", re.I)


def stated_figures(text: str, limit: int = 6) -> tuple[str, ...]:
    """The figures a clause states, in its own words and order ("15 days", "3
    consecutive days") — shown to the reader beside an UNKNOWN cap so a person sees
    what the engine saw. Display only: nothing here is compared or evaluated."""
    seen = dict.fromkeys(" ".join(m.group(0).split())
                         for m in _FIGURE.finditer(text or ""))
    return tuple(seen)[:limit]


def _sentence_start(body: str, at: int) -> int:
    """Where the sentence holding ``at`` begins (after the last "." or ";")."""
    stops = list(_STOP.finditer(body[:at]))
    return stops[-1].end() if stops else 0


def _sentence_stop(body: str, start: int) -> int:
    """Where the sentence holding ``start`` ends (its "." or ";"), or the body's end."""
    stop = _STOP.search(body, start)
    return stop.end() if stop else len(body)


def _same_sentence(body: str, anchor: tuple[int, int] | None,
                   span: tuple[int, int]) -> bool:
    """Whether ``span`` lies in the sentence (to the next "." or ";") that holds the
    cap phrase at ``anchor``."""
    if anchor is None:
        return False
    lo, hi = sorted((anchor[0], span[0]))
    return _STOP.search(body[lo:max(anchor[1], span[1])]) is None


def _phrase_span(body: str, phrases: tuple[str, ...]) -> tuple[int, int] | None:
    """Where the EARLIEST configured phrase occurs in the normalised body — the
    same boundary semantics as `contains_phrase` (35.5), as a span."""
    best: tuple[int, int] | None = None
    for phrase in phrases:
        needle = normalize(phrase)
        if not needle:
            continue
        match = re.search(phrase_pattern(needle), body)
        if match and (best is None or match.start() < best[0]):
            best = (match.start(), match.end())
    return best


def _states_second_figure(body: str, anchor: tuple[int, int],
                          quantity: tuple[int, int]) -> bool:
    """Whether a figure OTHER than the read quantity is written from the cap
    phrase to the end of the sentence stating that quantity (fail closed, 45B.4).
    A currency amount is never in the configured units, so it is caught here as
    a figure rather than through a currency vocabulary the engine would invent."""
    stop = re.compile(r"[.;](?:\s|$)").search(body, max(anchor[1], quantity[1]))
    end = stop.start() if stop else len(body)
    return any(not quantity[0] <= m.start() < quantity[1]
               for m in re.finditer(r"\d", body[:end]) if m.start() >= anchor[0])


def _find_magnitude(
    body: str,
    units: tuple[str, ...] | dict[str, tuple[str, ...]],
    anchor: tuple[int, int] | None = None,
) -> tuple[float, str, tuple[int, int]] | None:
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

    With no ``anchor`` returns the FIRST match in document order. With the span of
    the cap phrase (AM-62 r5, 2026-09-13) it returns the stated quantity NEAREST that
    phrase — a quantity overlapping the phrase first ("21 days of the invoice date"),
    then the smallest gap, the one after winning a tie ("at least thirty (30) days
    prior to the expiry of" reads 30) — so a clause stating several periods is read
    at the one its own cap phrase introduces. Deterministic either way (`ENG-11`).
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
    matches = list(pattern.finditer(body))
    if not matches:
        return None
    match = matches[0]
    if anchor is not None:
        # Nearest stated quantity to the phrase; one that OVERLAPS it ("21 days
        # of the invoice date" — the phrase carries the unit word) is distance 0.
        def distance(m: re.Match) -> tuple[int, int]:
            if m.end() > anchor[0] and m.start() < anchor[1]:
                return (0, 0)
            gap = m.start() - anchor[1] if m.start() >= anchor[1] else anchor[0] - m.end()
            return (gap, 0 if m.start() >= anchor[1] else 1)   # tie → the one after
        match = min(matches, key=distance)
    value = parse_number(match.group(1))
    if value is None:                                   # pragma: no cover
        return None
    return value, canonical_for[match.group(2)], match.span()


_UNITS_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
                "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
                "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
_TENS_WORDS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
               "seventy": 70, "eighty": 80, "ninety": 90}
_NUMBER_WORD = (r"(?:(?:" + "|".join(_TENS_WORDS) + r")(?:[- ](?:" + "|".join(
    k for k, v in _UNITS_WORDS.items() if v < 10) + r"))?|"
                + "|".join(_UNITS_WORDS) + r")")


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


def _find_basis(body: str, bases: dict[str, tuple[str, ...]]) -> str | None:
    """What the cap is measured against — locked 45B.4 ``cap_basis``.

    Returns ``None`` when no configured basis terminology matches. That matters:
    locked 45B.4 says "we should not assume equivalence between different bases", and
    ``RuleConfiguration.basis_is_comparable`` treats a ``None`` basis as
    non-comparable, so an unrecognised basis fails closed rather than being equated
    with the Company Standard's.

    A clause matching MORE than one basis ("total fees paid … for the specific
    services giving rise to the claim") states none of them unambiguously, so it
    returns ``None`` and fails closed — never the first key in sort order, which
    read an affected-services cap as total fees (A1, 45B.4).
    """
    matched = [basis for basis in bases
               if any(contains_phrase(body, term) for term in bases[basis])]
    return matched[0] if len(matched) == 1 else None


def _label(clause: Clause) -> str:
    return clause.section_number or str(clause.evidence_id)


def _about_this_term(body: str, config: LiabilityExtractionConfig) -> bool:
    """A sentence of the clause states a figure in the term's units AND is about the
    term: it names a basis or topic word, and a notice period says "notice". "Rolling
    90 days terms" is a renewal period, not the notice — that stays an absence (45C.14);
    "confidential for 5 years" is the survival in words no phrase reads — for a person."""
    basis = tuple(t for terms in config.bases.values() for t in terms)
    words = (*basis, *config.topic_terms)
    notice = any("NOTICE" in code for code in config.bases)

    def about(s: str) -> bool:
        if notice and _phrase_span(s, ("notice",)) is None:
            return False
        if _find_magnitude(s, config.units) is not None:
            return not words or _phrase_span(s, words) is not None
        # QA-018: a period in another unit ("payable within three (3) weeks of the
        # invoice date", "30 working days") is found, its figure unread — but only in a
        # sentence naming the term's OWN basis words; a topic word alone ("invoice")
        # also names its neighbours (the dispute window), as AB-104 accepted for units
        return (_PERIOD_FIGURE.search(s) is not None and bool(basis)
                and _phrase_span(s, basis) is not None and _beyond_basis(s, config))

    return any(about(s) for s in re.split(r"(?<=[.;])\s+", body))


def _beyond_basis(sentence: str, config: LiabilityExtractionConfig) -> bool:
    """The sentence names the topic in a word that is not a basis word — the basis word
    must be evidence of its own (as `_structural_signals`): "invoice" alone is in every
    billing sentence. No topic configured: nothing to require."""
    rest = _topic_beyond_basis(config)
    return not config.topic_terms or (
        bool(rest) and _phrase_span(sentence, rest) is not None)


def _names_topic(sentence: str, config: LiabilityExtractionConfig) -> bool:
    """A topic word beyond the basis word where the standard has one; otherwise any."""
    words = _topic_beyond_basis(config) or config.topic_terms
    return not words or _phrase_span(sentence, words) is not None


def _topic_beyond_basis(config: LiabilityExtractionConfig) -> tuple[str, ...]:
    basis = {normalize(t) for terms in config.bases.values() for t in terms}
    return tuple(t for t in config.topic_terms if normalize(t) not in basis)


def has_magnitude(body: str, units) -> bool:
    """A figure in these units anywhere in the normalised body (the structural signal)."""
    return _find_magnitude(body, units) is not None


def blank_in(body: str) -> bool:
    """A blank or bracketed figure ("[7] days", "_____ months") in the body."""
    return _blank_in(body)

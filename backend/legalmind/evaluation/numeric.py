"""`NUMERIC_COMPARISON` evaluator — locked Steps 45A, 45B, 45C.

Ordinal comparison of an extracted magnitude against configured thresholds.
``LIABILITY-001`` is the V1 occupant.

**No threshold, standard value or outcome is hardcoded.** Everything comes from
the Company Standard (42.8 JSONB) and the Legal Rule (42.9 JSONB) supplied in
the evaluator input. Locked Step 20 is explicit that "Actual Legal Rules must be
configured by authorized Legal/Admin users", and locked 45A §17's matrix is the
*configured* liability position, not a constant of the engine.

One Evaluation per governed scope (45C.1, A-4.3). Every absent configuration
value fails closed rather than defaulting (ENG-09).
"""

from __future__ import annotations

from dataclasses import replace

from legalmind.domain.enums import (
    EvaluationKind,
    ExtractionStatus,
    FindingClassification,
    RuleOutcome,
)
from legalmind.evaluation.contracts import (
    SCOPE_UNKNOWN,
    Cap,
    EvaluationResult,
    EvaluatorInput,
    EvaluatorOutput,
)
from legalmind.evaluation.rollup import roll_up
from legalmind.evaluation.rule_config import RuleConfiguration

# cap_status values (locked 45A §4 / 45B.4)
FINITE = "FINITE"
UNLIMITED = "UNLIMITED"
ABSENT = "ABSENT"
UNKNOWN = "UNKNOWN"

# Legal Rule configuration keys (locked 45B.9)
ACCEPTABLE_MAX = "acceptable_max"
ACCEPTABLE_MAX_UNIT = "acceptable_max_unit"
APPROVAL_REQUIRED_ABOVE = "approval_required_above"
UNLIMITED_OUTCOME = "unlimited_outcome"
DEVIATION_OUTCOME = "deviation_outcome"

# Company Standard configuration keys (locked 42.8 JSONB)
PREFERRED = "preferred"
UNIT = "unit"
BASIS = "basis"
SCOPE_KEY = "scope_key"


UNREADABLE = "UNREADABLE"


def document_side(cap: Cap, scope_key: str) -> dict:
    """What the document was actually found to say, in the shape `_compare`
    already uses for a MATCH.

    A comparability refusal is not an absence: the clause was read, and the
    reader is better served seeing "12 MONTHS of FEES_RECEIVED" beside the
    standard's "12 MONTHS of FEES_PAID" than seeing "Not recorded" twice. It
    explains the refusal instead of hiding it, and it asserts nothing about
    whether the two are equivalent — that is exactly what a human is being asked
    to decide (45B.4).
    """
    return {"cap_value": cap.cap_value, "cap_unit": cap.cap_unit,
            "cap_basis": cap.cap_basis, "scope": scope_key}


UNIT_CONVERSIONS = "unit_conversions"

#: AM-62 — the ONLY conversions the engine will perform, and only when the Company
#: Standard also declares the pair. Each is an identity of measure, not a legal
#: equivalence: a year is twelve months by definition; a month is not thirty
#: days by definition, so DAYS<->MONTHS is deliberately absent and can never be
#: declared into existence (rule 7).
DEFINITIONAL_UNIT_FACTORS: dict[tuple[str, str], float] = {
    ("YEARS", "MONTHS"): 12.0, ("MONTHS", "YEARS"): 1 / 12,
    ("WEEKS", "DAYS"): 7.0, ("DAYS", "WEEKS"): 1 / 7,
}


def declared_unit_factor(standard: dict, from_unit: str | None,
                         to_unit: str | None) -> float | None:
    """The factor that reads `from_unit` as `to_unit`, or None (fail closed).

    Both gates must open: the standard's `unit_conversions` lists the pair AND
    the pair is definitional. A declared pair the engine does not recognise is
    refused exactly like an undeclared one — configuration cannot widen what
    "the same quantity" means (44.29, 45C.23).
    """
    if from_unit is None or to_unit is None:
        return None
    for rule in standard.get(UNIT_CONVERSIONS) or ():
        if (isinstance(rule, dict) and rule.get("from_unit") == from_unit
                and rule.get("to_unit") == to_unit):
            return DEFINITIONAL_UNIT_FACTORS.get((from_unit, to_unit))
    return None


def standard_side(standard: dict) -> dict | None:
    """The organization's own position, for reporting alongside ANY result.

    A fail-closed result still has a knowable half: what we require. Until
    2026-09-13 the UNABLE branches reported neither side, so the Findings screen
    said "Company standard: Not recorded" for standards that plainly record one —
    measured on a live review, five findings whose standards declare 6 months,
    30 days and 12 months respectively. That is the screen stating something
    false about our own configuration, and it is independent of whether the
    document's value could be read.

    Returns None only when the standard genuinely declares no value, so
    "Not recorded" keeps exactly one meaning wherever it still appears. Nothing
    here reads the document, changes a classification or relaxes a refusal.
    """
    if standard.get(PREFERRED) is None:
        return None
    return {PREFERRED: standard.get(PREFERRED), UNIT: standard.get(UNIT),
            BASIS: standard.get(BASIS), SCOPE_KEY: standard.get(SCOPE_KEY)}


def evaluate_numeric(evaluator_input: EvaluatorInput) -> EvaluatorOutput:
    """Evaluate every scoped cap, producing one Evaluation per scope.

    Mapping provenance is stamped here, at the single entry point, rather than at
    each result construction site — there are four return paths and three of them are
    fail-closed, which are precisely the ones a per-site stamp would miss (D-2).
    """
    return _with_mapping_state(_evaluate(evaluator_input), evaluator_input)


def _evaluate(evaluator_input: EvaluatorInput) -> EvaluatorOutput:
    facts = evaluator_input.facts
    standard = evaluator_input.company_standard.configuration or {}
    legal_rule = evaluator_input.legal_rule
    rule_config = RuleConfiguration.from_config(
        legal_rule.rule_configuration if legal_rule else None)
    version = evaluator_input.evaluator_version

    if facts is None:
        return _single(_unable(
            evaluator_input, scope_key=standard.get(SCOPE_KEY) or SCOPE_UNKNOWN,
            reason="no extracted facts were supplied"), version)

    # 45B.7 — a FAILED extraction must produce UNABLE_TO_EVALUATE, never a guess.
    if facts.extraction_status is ExtractionStatus.FAILED:
        return _single(_unable(
            evaluator_input, scope_key=standard.get(SCOPE_KEY) or SCOPE_UNKNOWN,
            reason="extraction failed; facts are not usable",
            diagnostics=facts.extraction_diagnostics), version)

    # 45C.15 — no cap at all. Absence never manufactures a position.
    if not facts.caps:
        return _single(_absent(evaluator_input, standard), version)

    # 45C.2 — same-scope incompatibility is CONFLICT unless CONFIGURED
    # precedence resolves it. Detected but unresolvable precedence language
    # still yields CONFLICT (45C.27).
    results: list[EvaluationResult] = []
    for caps in _group_by_scope(facts.caps):
        if len(caps) > 1:
            resolved = _resolve_same_scope(caps, rule_config)
            if resolved is None:
                results.append(_conflict(evaluator_input, caps[0].scope, caps))
                continue
            caps = [resolved]
        results.append(_evaluate_cap(
            evaluator_input, caps[0], standard, legal_rule, rule_config))

    # Deterministic ordering so output is byte-stable (ENG-11).
    results.sort(key=lambda r: (r.evaluation_kind.value, r.scope_key,
                                r.scope_label or ""))
    return EvaluatorOutput(
        evaluations=tuple(results),
        finding_classification=roll_up([r.classification for r in results]),
        evaluator_version=version,
    )


# --------------------------------------------------------------- per-scope
def _evaluate_cap(evaluator_input, cap: Cap, standard: dict, legal_rule,
                  rule_config: RuleConfiguration) -> EvaluationResult:
    version = evaluator_input.evaluator_version
    scope_key = cap.scope
    base = {"scope_key": scope_key, "scope_label": cap.scope_label,
            "evaluation_kind": cap.cap_kind, "evaluator_version": version,
            "evidence_refs": cap.evidence_refs,
            "evidence_relationships": dict.fromkeys(cap.evidence_refs, "PRIMARY")}

    # 45C.20 — scope needed but undeterminable. AGGREGATE is never assumed.
    if cap.scope == SCOPE_UNKNOWN and rule_config.scope_required:
        return _result(base, FindingClassification.UNABLE_TO_EVALUATE,
                       RuleOutcome.NOT_APPLICABLE,
                       expected_value=standard_side(standard),
                       explanation=("scope could not be determined and the "
                                    "configured comparison requires it",
                                    "scope is not assumed (45C.20)"))

    if cap.cap_status == UNKNOWN:
        return _result(base, FindingClassification.UNABLE_TO_EVALUATE,
                       RuleOutcome.NOT_APPLICABLE,
                       expected_value=standard_side(standard),
                       actual_value={"cap_status": UNREADABLE, "scope": scope_key},
                       explanation=("cap could not be reliably interpreted",))

    # 45C.4 — an UNLIMITED carve-out applies ONLY to its own scope and never
    # generalizes to the whole provision.
    if cap.cap_status == UNLIMITED:
        outcome = _unlimited_outcome(legal_rule)
        return _result(base, FindingClassification.DEVIATION, outcome,
                       expected_value={PREFERRED: standard.get(PREFERRED),
                                       UNIT: standard.get(UNIT)},
                       actual_value={"cap_status": UNLIMITED},
                       operator="unlimited",
                       explanation=(
                           f"cap is UNLIMITED for scope {scope_key}",
                           f"configured unlimited outcome: {outcome.value}",
                           "this position applies only to this scope (45C.4)"))

    if cap.cap_status == ABSENT:
        return _result(base, FindingClassification.MISSING,
                       RuleOutcome.NOT_APPLICABLE,
                       explanation=(f"no qualifying cap for scope {scope_key}",))

    # ---- FINITE from here on ----
    if cap.cap_value is None or cap.cap_unit is None:
        # 45C.19 — a bare quantity without its qualifier is insufficient.
        return _result(base, FindingClassification.UNABLE_TO_EVALUATE,
                       RuleOutcome.NOT_APPLICABLE,
                       expected_value=standard_side(standard),
                       actual_value={"cap_status": UNREADABLE, "scope": scope_key},
                       explanation=("cap value or unit is missing; a bare "
                                    "quantity is insufficient (45C.19)",))

    standard_scope = standard.get(SCOPE_KEY)
    if not rule_config.scope_is_comparable(scope_key, standard_scope):
        # 45C.5 / 45C.6 — values in incomparable scopes must not be compared.
        return _result(base, FindingClassification.UNABLE_TO_EVALUATE,
                       RuleOutcome.NOT_APPLICABLE,
                       expected_value=standard_side(standard),
                       actual_value=document_side(cap, scope_key),
                       explanation=(
                           f"scope {scope_key} is not comparable to the Company "
                           f"Standard scope {standard_scope}",
                           "no cross-scope comparison is performed (45C.5)"))

    unit_note: str | None = None
    if cap.cap_unit != standard.get(UNIT):
        # AM-62 — a DECLARED, DEFINITIONAL conversion is not a silent one. The
        # standard must declare the pair, the pair must be one the engine knows
        # to be an identity of measure (a year IS twelve months), and the
        # arithmetic is done here, in tested code (44.29). Anything else stays
        # exactly where 45C.23 left it: UNABLE_TO_EVALUATE, a person decides.
        factor = declared_unit_factor(standard, cap.cap_unit, standard.get(UNIT))
        if factor is None:
            return _result(base, FindingClassification.UNABLE_TO_EVALUATE,
                           RuleOutcome.NOT_APPLICABLE,
                           expected_value=standard_side(standard),
                           actual_value=document_side(cap, scope_key),
                           explanation=(
                               f"unit {cap.cap_unit} differs from the Company "
                               f"Standard unit {standard.get(UNIT)}",
                               "units are not converted without a declared, "
                               "definitional conversion (45C.23, AM-62)"))
        assert cap.cap_value is not None
        unit_note = (f"{cap.cap_value:g} {cap.cap_unit} read as "
                      f"{cap.cap_value * factor:g} {standard.get(UNIT)} under the "
                      f"declared conversion (1 {cap.cap_unit} = {factor:g} "
                      f"{standard.get(UNIT)}; AM-62)")
        cap = replace(cap, cap_value=cap.cap_value * factor, cap_unit=standard.get(UNIT))

    standard_basis = standard.get(BASIS)
    if not rule_config.basis_is_comparable(cap.cap_basis, standard_basis):
        # 45C.7 / 45C.8 — no conversion without a configured rule AND its inputs.
        conversion = rule_config.conversion_for(cap.cap_basis, standard_basis)
        detail = ("no configured conversion rule permits comparing basis "
                  f"{cap.cap_basis} with {standard_basis}"
                  if conversion is None else
                  "a conversion rule exists but its required inputs are "
                  f"unavailable: {list(conversion.required_inputs)}")
        return _result(base, FindingClassification.UNABLE_TO_EVALUATE,
                       RuleOutcome.NOT_APPLICABLE,
                       expected_value=standard_side(standard),
                       actual_value=document_side(cap, scope_key),
                       explanation=(detail, "bases are not assumed equivalent "
                                            "(45B.4, 45C.23)"))

    return _compare(base, cap, standard, legal_rule, scope_key, conversion=unit_note)


def _compare(base, cap: Cap, standard: dict, legal_rule,
             scope_key: str, conversion: str | None = None) -> EvaluationResult:
    """The ordinal comparison. Thresholds are configuration (45B.9).

    `conversion` is the AM-62 sentence when the document's quantity was read in a
    different, declared unit; it travels in the explanation so the reader sees
    the document's own words AND the arithmetic that made them comparable.
    """
    preferred = standard.get(PREFERRED)
    if preferred is None:
        return _result(base, FindingClassification.UNABLE_TO_EVALUATE,
                       RuleOutcome.NOT_APPLICABLE,
                       explanation=("Company Standard declares no preferred "
                                    "value for this Requirement",))

    # Non-None from here: the FINITE branch above returns UNABLE_TO_EVALUATE when
    # either the value or the unit is missing (45C.19).
    assert cap.cap_value is not None
    actual: float = cap.cap_value
    expected = {PREFERRED: preferred, UNIT: standard.get(UNIT),
                BASIS: standard.get(BASIS), SCOPE_KEY: standard.get(SCOPE_KEY)}
    actual_value = {"cap_value": actual, "cap_unit": cap.cap_unit,
                    "cap_basis": cap.cap_basis, "scope": scope_key}
    converted: tuple[str, ...] = (conversion,) if conversion else ()

    if actual == preferred:
        return _result(base, FindingClassification.MATCH,
                       RuleOutcome.NOT_APPLICABLE,
                       expected_value=expected, actual_value=actual_value,
                       operator="==",
                       comparison={"expected": preferred, "actual": actual,
                                   "operator": "==", "result": True,
                                   **({"conversion": conversion} if conversion else {})},
                       explanation=(f"{actual} {cap.cap_unit} equals the Company "
                                    f"Standard of {preferred}", *converted))

    outcome, rule_detail = _rule_outcome_for(actual, legal_rule)
    return _result(base, FindingClassification.DEVIATION, outcome,
                   expected_value=expected, actual_value=actual_value,
                   operator="!=",
                   comparison={"expected": preferred, "actual": actual,
                               "operator": "!=", "result": True,
                               "rule": rule_detail},
                   explanation=(
                       f"{actual} {cap.cap_unit} differs from the Company "
                       f"Standard of {preferred}",
                       f"configured rule outcome: {outcome.value}"
                       + (f" ({rule_detail})" if rule_detail else ""),
                       *converted))


def _rule_outcome_for(actual: float, legal_rule) -> tuple[RuleOutcome, str]:
    """Map a deviation onto a configured Rule Outcome.

    Locked Step 20 r4: not every Clause requires a Pre-approved Legal Rule. With
    no rule the outcome is NOT_APPLICABLE — the deviation stands and a human
    decides. The engine never invents a tolerance.
    """
    if legal_rule is None:
        return RuleOutcome.NOT_APPLICABLE, "no Legal Rule configured"
    cfg = legal_rule.configuration or {}

    # `deviation_outcome` — the ZERO-TOLERANCE key (manager ruling, recorded
    # 2026-08-19: "whatever is stated in our approved legal documents is the
    # final position"; any deviation -> UNACCEPTABLE -> Legal Decision). It
    # exists because the threshold keys CANNOT express zero tolerance:
    # `acceptable_max = preferred` would wrongly ACCEPT below-preferred values.
    # Checked first, deliberately: a blanket disposition and a threshold band in
    # one rule would contradict each other, and the blanket one is the stated
    # policy. This only maps an ALREADY-DETECTED deviation onto an outcome —
    # the comparison itself is untouched, and MATCH never reaches here.
    blanket = cfg.get(DEVIATION_OUTCOME)
    if blanket is not None:
        # `AM-33` r3: a DEVIATION never maps to ACCEPTABLE through ANY rule form.
        # ACCEPTABLE is reachable only from MATCH; a blanket that says otherwise
        # is a misconfiguration and fails closed to a human, exactly like a band.
        if blanket == RuleOutcome.ACCEPTABLE.value:
            return (RuleOutcome.NOT_APPLICABLE,
                    "deviation_outcome ACCEPTABLE is not an authorized "
                    "disposition (AM-33 r3); treated as unruled")
        try:
            return (RuleOutcome(blanket),
                    f"deviation_outcome {blanket} (zero-tolerance rule)")
        except ValueError:
            # An unrecognised outcome is a misconfiguration, not permission to
            # guess: fall through to NOT_APPLICABLE and a human (ENG-09).
            return (RuleOutcome.NOT_APPLICABLE,
                    f"deviation_outcome {blanket!r} is not a valid RuleOutcome; "
                    "treated as unruled")

    # `AM-33` (AB-6, owner 2026-08-31): the threshold-band rule form is withdrawn.
    # A rule carrying a band key is never interpreted — the deviation stands and a
    # human decides (r2). The keys remain named so the refusal is explicit rather
    # than a silent unknown-key fallthrough.
    if any(cfg.get(key) is not None
           for key in (APPROVAL_REQUIRED_ABOVE, ACCEPTABLE_MAX, ACCEPTABLE_MAX_UNIT)):
        return (RuleOutcome.NOT_APPLICABLE,
                "tolerance-band keys are not an authorized rule form (AM-33); "
                "treated as unruled")
    return RuleOutcome.NOT_APPLICABLE, "no authorized rule disposition configured"


def _unlimited_outcome(legal_rule) -> RuleOutcome:
    """The unlimited position is configuration (45B.9 `unlimited_outcome`)."""
    if legal_rule is None:
        return RuleOutcome.NOT_APPLICABLE
    raw = (legal_rule.configuration or {}).get(UNLIMITED_OUTCOME)
    if raw is None:
        return RuleOutcome.NOT_APPLICABLE
    try:
        return RuleOutcome(raw)
    except ValueError:
        return RuleOutcome.NOT_APPLICABLE


# ------------------------------------------------------- scope grouping etc.
def _group_by_scope(caps: tuple[Cap, ...]) -> list[list[Cap]]:
    """Group caps that govern the SAME scope.

    45C.1 — differing values across DIFFERENT scopes are not a conflict; only
    same-scope incompatibility is (45C.2). A carve-out therefore never conflicts
    with the general cap, because kind and label are part of the grouping key.

    Returns groups in deterministic key order (ENG-11).
    """
    grouped: dict[tuple[str, str, str], list[Cap]] = {}
    for cap in caps:
        key = (cap.cap_kind.value, cap.scope, cap.scope_label or "")
        grouped.setdefault(key, []).append(cap)
    return [grouped[k] for k in sorted(grouped)]


def _resolve_same_scope(caps: list[Cap],
                        rule_config: RuleConfiguration) -> Cap | None:
    """Resolve same-scope caps, or None => CONFLICT.

    45C.17 — materially identical restatements are ONE position, not a conflict.
    45C.22 / F-6 — otherwise only CONFIGURED precedence may resolve it; in-document
    precedence language is never applied.
    """
    distinct = {(c.cap_status, c.cap_value, c.cap_unit, c.cap_basis) for c in caps}
    if len(distinct) == 1:
        merged_evidence = tuple(dict.fromkeys(
            e for c in caps for e in c.evidence_refs))
        return replace(caps[0], evidence_refs=merged_evidence)
    return None      # incompatible: CONFLICT. No precedence heuristic.


# ------------------------------------------------------------- result helpers
def _result(base: dict, classification, outcome, **kwargs) -> EvaluationResult:
    return EvaluationResult(classification=classification, rule_outcome=outcome,
                            **base, **kwargs)


def _conflict(evaluator_input, scope_key: str,
              caps: list[Cap]) -> EvaluationResult:
    """45C.2 / 45C.27 — all evidence retained, nothing discarded."""
    evidence = tuple(dict.fromkeys(e for c in caps for e in c.evidence_refs))
    return EvaluationResult(
        scope_key=scope_key, scope_label=caps[0].scope_label,
        evaluation_kind=caps[0].cap_kind,
        classification=FindingClassification.CONFLICT,
        rule_outcome=RuleOutcome.NOT_APPLICABLE,
        evaluator_version=evaluator_input.evaluator_version,
        actual_value={"caps": [
            {"cap_status": c.cap_status, "cap_value": c.cap_value,
             "cap_unit": c.cap_unit, "cap_basis": c.cap_basis} for c in caps]},
        evidence_refs=evidence,
        # Every conflicting provision is retained as CONFLICTING evidence.
        evidence_relationships=dict.fromkeys(evidence, "CONFLICTING"),
        explanation=(
            f"{len(caps)} incompatible provisions govern scope {scope_key}",
            "no configured precedence rule resolves them; reported as CONFLICT",
            "all conflicting provisions retained as evidence (45C.2)"),
        diagnostics=("no configured precedence rule applied",))


def _absent(evaluator_input, standard: dict) -> EvaluationResult:
    """45C.15 — wholly absent. ZERO evidence is the correct representation."""
    return EvaluationResult(
        scope_key=standard.get(SCOPE_KEY) or SCOPE_UNKNOWN,
        evaluation_kind=EvaluationKind.PRIMARY,
        classification=FindingClassification.MISSING,
        rule_outcome=RuleOutcome.NOT_APPLICABLE,
        evaluator_version=evaluator_input.evaluator_version,
        expected_value={PREFERRED: standard.get(PREFERRED),
                        UNIT: standard.get(UNIT)},
        actual_value={"cap_status": ABSENT},
        evidence_refs=(),                      # nothing to attach; none invented
        explanation=("no qualifying provision was extracted",
                     "absence never manufactures a substantive position (45C.15)"),
    )


def _unable(evaluator_input, *, scope_key: str, reason: str,
            diagnostics: tuple[str, ...] = ()) -> EvaluationResult:
    return EvaluationResult(
        scope_key=scope_key, evaluation_kind=EvaluationKind.PRIMARY,
        classification=FindingClassification.UNABLE_TO_EVALUATE,
        rule_outcome=RuleOutcome.NOT_APPLICABLE,
        evaluator_version=evaluator_input.evaluator_version,
        evidence_refs=tuple(r.evidence_id for r in evaluator_input.evidence),
        expected_value=standard_side(
            evaluator_input.company_standard.configuration or {}),
        explanation=(reason, "failing closed rather than guessing (ENG-09)"),
        diagnostics=diagnostics)


def _single(result: EvaluationResult, version: str) -> EvaluatorOutput:
    return EvaluatorOutput(evaluations=(result,),
                           finding_classification=roll_up([result.classification]),
                           evaluator_version=version)


# --------------------------------------------------------- mapping provenance
def _with_mapping_state(output: EvaluatorOutput,
                        evaluator_input: EvaluatorInput) -> EvaluatorOutput:
    """Record which Mapping State this evaluation was built on — owner decision D-2.

    `REC-03` calls `CONFIRMED`/`AMBIGUOUS`/`UNRESOLVED` the canonical **persisted**
    mapping vocabulary, but no locked table carries a column for it. D-2 keeps it in
    `evaluations.result.evaluated_facts`, which the append-only Evaluation record
    already preserves — so a replay can show what mapping concluded without an
    amendment. `PRESENCE` has always written it; this is the numeric side.

    **Provenance only.** Nothing here reads the state to influence a classification:
    presence is the mapping layer's business (45D) and this evaluator's inputs are
    facts. Stamped in one place, after every result is built, so no construction
    path can omit it.
    """
    mapping = evaluator_input.mapping
    if mapping is None:
        return output
    stamped = tuple(
        replace(result,
                evaluated_facts={**(result.evaluated_facts or {}),
                                 "mapping_state": mapping.mapping_state.value})
        for result in output.evaluations
    )
    return replace(output, evaluations=stamped)

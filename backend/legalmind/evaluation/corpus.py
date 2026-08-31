"""Golden corpus runner — locked ENG-12, Step 45E, Step 54.

Locked Step 54.1 makes the corpus **Tier 1 and normative**: a diff in an expected
output is a specification change, reviewed as such, never edited to make a build
pass.

Locked Step 45E.1 fixes the universal assertion rule:

    Every case asserts BOTH the exact set of scoped Evaluation outputs AND the
    derived Finding summary. NEVER the roll-up alone.

The roll-up is lossy by design, so a fixture asserting only the summary would let
per-scope regressions pass undetected. ``run_fixture`` therefore fails if a
fixture omits ``expect_evaluations``.

------------------------------------------------------------------------------
Fixture provenance
------------------------------------------------------------------------------
A fixture's expected outputs are legal conclusions. Under Step 54 they become
normative and bind every later change, so they must be authored from real
representative contracts and the organization's real Company Standards.

Four provenance values, in increasing legal weight. The owner's instruction of
2026-08-18 required that every expected output declare which of these it is,
rather than leaving the basis implicit in a description:

``STRUCTURAL``
    Exercises the algorithm with placeholder values that carry no legal meaning.

``DOCUMENT_SUPPORTED``
    The expected output follows from **real supplied document text plus the
    locked engine specification alone**, with no Company Standard *value*
    involved. In practice these are the fail-closed, conflict and absence paths:
    the engine's answer does not depend on what the organization will accept, so
    no acceptance position has to be assumed to author one. Must cite
    ``source_document`` and ``source_clause``.

``STANDARD_DERIVED``
    The expected output is computed mechanically from a Company Standard position
    the supplied documents **explicitly state** — a `MATCH` or `DEVIATION`
    classification. Requires ``preferred``.

    Per the owner's V1 policy of 2026-08-18 — *"I do not currently have a formally
    approved LeapSwitch Company Acceptance Policy or Legal Rule"* — such a fixture
    may state **what a clause is** but never **what Legal should do about it**. It
    therefore must NOT carry ``acceptable_max``, ``approval_required_above`` or
    ``unlimited_outcome``, and every expected ``rule_outcome`` must be
    ``NOT_APPLICABLE``. That is not a placeholder: locked Step 20 r4 makes
    ``NOT_APPLICABLE`` mean precisely *"no Pre-approved Legal Rule; the deviation
    stands and a human decides"*, which is the fail-closed state the policy asks
    for. No fifth enum value is needed and none was added (45B.26).

``NORMATIVE``
    Full conformance fixture per Step 45E — real contracts, a real Company
    Standard **and** an approved Legal Rule, so a Rule Outcome other than
    ``NOT_APPLICABLE`` becomes assertable for the first time.

The tiers separate the two axes the owner required be kept apart: ``classification``
(MATCH/DEVIATION/…) is reachable at ``STANDARD_DERIVED``; ``rule_outcome`` beyond
``NOT_APPLICABLE`` is reachable only at ``NORMATIVE``.

The distinction that matters: a `DOCUMENT_SUPPORTED` fixture asserts *"given this
real clause and no stated acceptance position, the engine fails closed like
this"*. It never asserts that a value is acceptable, and so it cannot smuggle in
an invented legal position.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from legalmind.domain.enums import (
    EvaluationKind,
    EvaluatorType,
    ExtractionStatus,
    FindingClassification,
    MappingState,
    RuleOutcome,
)
from legalmind.evaluation.contracts import (
    Cap,
    CompanyStandard,
    EvaluatorInput,
    EvidenceRef,
    LegalRule,
    LiabilityFacts,
    MappingInput,
    RequirementContext,
)
from legalmind.evaluation.registry import evaluate, version_for

STRUCTURAL = "STRUCTURAL"
DOCUMENT_SUPPORTED = "DOCUMENT_SUPPORTED"
STANDARD_DERIVED = "STANDARD_DERIVED"
NORMATIVE = "NORMATIVE"

PROVENANCE_VALUES = frozenset(
    {STRUCTURAL, DOCUMENT_SUPPORTED, STANDARD_DERIVED, NORMATIVE})

# Provenance values whose expected outputs are legal conclusions about real
# material, and which 45E.7 rule 1 therefore requires to pin their source.
TRACEABLE_PROVENANCE = frozenset({DOCUMENT_SUPPORTED, STANDARD_DERIVED, NORMATIVE})


#: Ratified Company Standard configuration, supplied by the owner. Referenced by
#: `company_standard_ref` so a standard is stated once and cannot drift between
#: fixtures (45E.7 rule 1 requires each fixture to pin its configuration; pinning
#: to one file is how that is kept true).
RATIFIED_STANDARDS_DIR = (
    Path(__file__).resolve().parents[2] / "config" / "company_standards")


class FixtureError(Exception):
    """A fixture is malformed or omits a required assertion."""


def ratified_standard(requirement_code: str) -> dict[str, Any]:
    """Load a ratified Company Standard's `configuration` block by code.

    Raises rather than defaulting: a fixture referencing a standard that does not
    exist must fail loudly, never fall back to an empty standard, which would
    silently turn a MATCH assertion into a fail-closed one.
    """
    path = RATIFIED_STANDARDS_DIR / f"{requirement_code}.json"
    if not path.exists():
        raise FixtureError(
            f"no ratified Company Standard for {requirement_code!r} at {path}. "
            "A ratified standard is the organization's own position and must be "
            "supplied by the owner (rule 21); it is never defaulted.")
    payload = json.loads(path.read_text())
    config = payload.get("configuration")
    if not config:
        raise FixtureError(f"{path} declares no `configuration` block")
    return dict(config)


@dataclass(frozen=True)
class ExpectedEvaluation:
    scope_key: str
    classification: FindingClassification
    rule_outcome: RuleOutcome
    evaluation_kind: EvaluationKind = EvaluationKind.PRIMARY
    scope_label: str | None = None
    evidence_ref_count: int | None = None


@dataclass(frozen=True)
class Fixture:
    id: str
    description: str
    provenance: str
    evaluator_input: EvaluatorInput
    expect_finding_classification: FindingClassification
    expect_evaluations: tuple[ExpectedEvaluation, ...]
    source: str | None = None
    # Provenance trail for a fixture built from real material (45E.7 rule 1).
    source_document: str | None = None
    source_clause: str | None = None
    # The Step 45E fixture ids this case covers, so coverage is checkable rather
    # than asserted in prose.
    covers: tuple[str, ...] = ()


@dataclass
class FixtureOutcome:
    fixture_id: str
    passed: bool
    failures: list[str] = field(default_factory=list)


def run_fixture(fixture: Fixture) -> FixtureOutcome:
    """Execute one fixture, asserting both levels (45E.1)."""
    if not fixture.expect_evaluations:
        raise FixtureError(
            f"{fixture.id}: expect_evaluations is required — asserting only the "
            "rolled-up Finding classification would hide per-scope regressions "
            "(Step 45E.1)")

    output = evaluate(fixture.evaluator_input)
    failures: list[str] = []

    if output.finding_classification is not fixture.expect_finding_classification:
        failures.append(
            f"finding classification: expected "
            f"{fixture.expect_finding_classification.value}, got "
            f"{output.finding_classification.value}")

    actual = {
        (e.scope_key, e.scope_label, e.evaluation_kind): e
        for e in output.evaluations
    }
    expected = {
        (x.scope_key, x.scope_label, x.evaluation_kind): x
        for x in fixture.expect_evaluations
    }

    for key in expected.keys() - actual.keys():
        failures.append(f"missing evaluation for scope {key}")
    for key in actual.keys() - expected.keys():
        failures.append(f"unexpected evaluation for scope {key}")

    for key in expected.keys() & actual.keys():
        want, got = expected[key], actual[key]
        if got.classification is not want.classification:
            failures.append(f"{key} classification: expected "
                            f"{want.classification.value}, got "
                            f"{got.classification.value}")
        if got.rule_outcome is not want.rule_outcome:
            failures.append(f"{key} rule_outcome: expected "
                            f"{want.rule_outcome.value}, got "
                            f"{got.rule_outcome.value}")
        if (want.evidence_ref_count is not None
                and len(got.evidence_refs) != want.evidence_ref_count):
            failures.append(f"{key} evidence count: expected "
                            f"{want.evidence_ref_count}, got "
                            f"{len(got.evidence_refs)}")

    # Structural invariants asserted for EVERY fixture (45E.4 R-09/R-11).
    if not output.evaluations:
        failures.append("EV-MIN: no evaluations produced")
    for e in output.evaluations:
        if not e.evaluator_version:
            failures.append(f"{e.scope_key}: evaluator_version missing (AM-19)")
        if (not e.evidence_refs
                and e.classification is not FindingClassification.MISSING):
            failures.append(
                f"{e.scope_key}: {e.classification.value} has no evidence; only "
                "MISSING-by-absence may be empty (N-34)")

    return FixtureOutcome(fixture_id=fixture.id, passed=not failures,
                          failures=failures)


def run_corpus(fixtures: list[Fixture]) -> list[FixtureOutcome]:
    return [run_fixture(f) for f in fixtures]


# --------------------------------------------------------------------------
# Fixture loading
# --------------------------------------------------------------------------
def load_fixture(payload: dict[str, Any]) -> Fixture:
    """Build a Fixture from its serialized form.

    Deliberately strict: an unknown provenance, a missing evaluator type or an
    absent ``expect_evaluations`` is an error rather than a default, so a
    malformed normative fixture cannot silently become a weaker assertion.
    """
    provenance = payload.get("provenance")
    if provenance not in PROVENANCE_VALUES:
        raise FixtureError(
            f"{payload.get('id')}: provenance must be one of "
            f"{sorted(PROVENANCE_VALUES)}")

    # 45E.7 rule 1 — a fixture asserting a conclusion about real material must
    # name the material. Without this a DOCUMENT_SUPPORTED label is unfalsifiable.
    if provenance in TRACEABLE_PROVENANCE and not (
            payload.get("source_document") and payload.get("source_clause")):
        raise FixtureError(
            f"{payload.get('id')}: {provenance} requires source_document and "
            "source_clause so the expected output is traceable to the material "
            "it was derived from (45E.7 rule 1)")

    evaluator_type = EvaluatorType(payload["evaluator_type"])
    requirement = RequirementContext(
        requirement_version_id=UUID(payload["requirement_version_id"])
        if payload.get("requirement_version_id") else uuid4(),
        code=payload["requirement_code"],
        evaluator_type=evaluator_type,
        required=bool(payload.get("required", True)))

    if payload.get("company_standard") and payload.get("company_standard_ref"):
        raise FixtureError(
            f"{payload.get('id')}: supply company_standard or "
            "company_standard_ref, not both — two sources of truth for one "
            "standard is exactly the drift the ref exists to prevent.")
    standard_config = (
        ratified_standard(payload["company_standard_ref"])
        if payload.get("company_standard_ref")
        else (payload.get("company_standard") or {}))
    standard = CompanyStandard(version_id=uuid4(), configuration=standard_config)
    legal_rule = None
    if payload.get("legal_rule") is not None:
        legal_rule = LegalRule(
            version_id=uuid4(),
            configuration=payload["legal_rule"].get("configuration") or {},
            rule_configuration=payload["legal_rule"].get("rule_configuration") or {})

    evidence = tuple(EvidenceRef(evidence_id=uuid4())
                     for _ in range(int(payload.get("evidence_count", 0))))

    facts = None
    mapping = None
    if evaluator_type is EvaluatorType.NUMERIC_COMPARISON:
        caps = []
        for raw in payload.get("caps") or []:
            refs = tuple(uuid4() for _ in range(int(raw.get("evidence_count", 1))))
            caps.append(Cap(
                cap_kind=EvaluationKind(raw.get("cap_kind", "PRIMARY")),
                scope=raw["scope"], cap_status=raw["cap_status"],
                scope_label=raw.get("scope_label"),
                cap_value=raw.get("cap_value"), cap_unit=raw.get("cap_unit"),
                cap_basis=raw.get("cap_basis"), evidence_refs=refs))
        facts = LiabilityFacts(
            caps=tuple(caps),
            extraction_status=ExtractionStatus(
                payload.get("extraction_status", "COMPLETE")),
            extraction_diagnostics=tuple(payload.get("extraction_diagnostics") or ()))
    else:
        mapping = MappingInput(
            mapping_state=MappingState(payload["mapping_state"]),
            evidence_refs=evidence)

    expected = tuple(
        ExpectedEvaluation(
            scope_key=x["scope_key"],
            classification=FindingClassification(x["classification"]),
            rule_outcome=RuleOutcome(x["rule_outcome"]),
            evaluation_kind=EvaluationKind(x.get("evaluation_kind", "PRIMARY")),
            scope_label=x.get("scope_label"),
            evidence_ref_count=x.get("evidence_ref_count"))
        for x in payload.get("expect_evaluations") or ())

    _check_provenance_invariants(payload, provenance, expected, standard_config)

    return Fixture(
        id=payload["id"],
        description=payload.get("description", ""),
        provenance=provenance,
        source_document=payload.get("source_document"),
        source_clause=payload.get("source_clause"),
        covers=tuple(payload.get("covers") or ()),
        evaluator_input=EvaluatorInput(
            requirement=requirement, company_standard=standard,
            evaluator_version=version_for(evaluator_type),
            evidence=evidence, facts=facts, mapping=mapping,
            legal_rule=legal_rule),
        expect_finding_classification=FindingClassification(
            payload["expect_finding_classification"]),
        expect_evaluations=expected,
        source=payload.get("source"))


#: Company Standard / Legal Rule keys that state what the organization will
#: ACCEPT, as opposed to vocabulary describing how a value is expressed. Only the
#: owner can supply these (rule 21); a DOCUMENT_SUPPORTED fixture must not carry
#: one, or it would assert an acceptance position the owner never stated.
# `preferred` states a numeric position; `expected_presence` states a presence
# position (Step 28's two evaluator families). Either makes a standard a POSITION.
ACCEPTANCE_POSITION_KEYS = ("preferred", "expected_presence")
ACCEPTANCE_RULE_KEYS = ("acceptable_max", "approval_required_above",
                        "unlimited_outcome", "deviation_outcome")

#: The ONE approved Legal Rule (owner approval, 2026-08-20, confirming the
#: manager's zero-tolerance ruling of 2026-08-19): MATCH is acceptable, ANY
#: deviation — unlimited included — is UNACCEPTABLE and goes to Legal. No
#: tolerance band exists BY POLICY, so `acceptable_max` and
#: `approval_required_above` remain forbidden on every pre-NORMATIVE tier: the
#: approved rule is admitted EXACTLY as stated, never approximated.
APPROVED_ZERO_TOLERANCE_RULE = {
    "deviation_outcome": "UNACCEPTABLE",
    "unlimited_outcome": "UNACCEPTABLE",
}


def _check_provenance_invariants(
        payload: dict[str, Any], provenance: str,
        expected: tuple[ExpectedEvaluation, ...],
        standard: dict[str, Any]) -> None:
    """Make the provenance label enforceable rather than decorative.

    Without this, ``DOCUMENT_SUPPORTED`` would be a comment: someone could set a
    ``preferred`` value drawn from the organization's own outbound contract, get a
    `MATCH`, and label it as derived from the document. That is precisely the
    inversion the owner ruled out on 2026-08-18 — a cap a vendor grants itself is
    not a standard the vendor demands — so it is refused mechanically.

    The second half enforces the owner's V1 policy: until a Legal Rule is
    approved, no fixture may assert what Legal should do about a deviation.
    """
    fixture_id = payload.get("id")
    rule_cfg = ((payload.get("legal_rule") or {}).get("configuration") or {})

    has_position = any(standard.get(k) is not None
                       for k in ACCEPTANCE_POSITION_KEYS)

    # `AM-33` (AB-6, 2026-08-31) — the threshold-band rule form is withdrawn for
    # EVERY tier, STRUCTURAL included: structural fixtures exercise vocabulary
    # through the authorized blanket form only (r6). The engine would refuse to
    # interpret a band anyway (r2); refusing it here keeps the corpus honest
    # about what forms exist at all.
    for key in ("acceptable_max", "acceptable_max_unit", "approval_required_above"):
        if rule_cfg.get(key) is not None:
            raise FixtureError(
                f"{fixture_id}: legal_rule.configuration.{key} is a withdrawn "
                "tolerance-band key (AM-33 r6) — no tier may carry it. Use the "
                "blanket dispositions deviation_outcome / unlimited_outcome.")

    if provenance == DOCUMENT_SUPPORTED:
        for key in ACCEPTANCE_POSITION_KEYS:
            if standard.get(key) is not None:
                raise FixtureError(
                    f"{fixture_id}: a {DOCUMENT_SUPPORTED} fixture must not "
                    f"supply company_standard.{key} — that states a position, and "
                    f"this tier asserts only what follows from the document text "
                    f"alone. Use {STANDARD_DERIVED} when the position is one the "
                    "supplied documents explicitly state.")
        for x in expected:
            if x.classification is FindingClassification.MATCH:
                raise FixtureError(
                    f"{fixture_id}: a {DOCUMENT_SUPPORTED} fixture cannot "
                    f"expect MATCH for scope {x.scope_key} — MATCH means the "
                    "provision aligns with a Company Standard, and this tier "
                    "supplies none.")

    if provenance == STANDARD_DERIVED and not has_position:
        raise FixtureError(
            f"{fixture_id}: {STANDARD_DERIVED} asserts a conclusion computed "
            "from a stated Company Standard position, but none is present. If the "
            f"expectation follows from the document alone, use {DOCUMENT_SUPPORTED}.")

    # Applies to both pre-NORMATIVE tiers. Since 2026-08-20 ONE Legal Rule is
    # approved — the zero-tolerance blanket — and a fixture may carry it EXACTLY
    # as approved, on the tier that states a position (STANDARD_DERIVED). No
    # tolerance band exists by policy, so the threshold keys stay forbidden
    # everywhere below NORMATIVE, and any other disposition value is refused.
    if provenance in {DOCUMENT_SUPPORTED, STANDARD_DERIVED}:
        carries_approved_rule = (
            provenance == STANDARD_DERIVED
            and rule_cfg == APPROVED_ZERO_TOLERANCE_RULE)
        if rule_cfg and not carries_approved_rule:
            raise FixtureError(
                    f"{fixture_id}: {provenance} may carry a Legal Rule only as "
                    f"the approved zero-tolerance rule, verbatim "
                    f"({APPROVED_ZERO_TOLERANCE_RULE}), and only on "
                    f"{STANDARD_DERIVED}. A tolerance band or any other "
                    "disposition is an acceptance policy nobody approved "
                    "(owner rulings 2026-08-18/2026-08-20); thresholds are "
                    "never inferred from a document.")
        allowed_outcomes = {RuleOutcome.NOT_APPLICABLE}
        if carries_approved_rule:
            # Exactly what the approved rule can produce: MATCH -> ACCEPTABLE,
            # DEVIATION (unlimited included) -> UNACCEPTABLE.
            allowed_outcomes |= {RuleOutcome.ACCEPTABLE, RuleOutcome.UNACCEPTABLE}
        for x in expected:
            if x.rule_outcome not in allowed_outcomes:
                raise FixtureError(
                    f"{fixture_id}: {provenance} cannot expect rule_outcome "
                    f"{x.rule_outcome.value} for scope {x.scope_key}. Without "
                    "the approved rule the locked outcome is NOT_APPLICABLE — "
                    "the deviation stands and a human decides (Step 20 r4); "
                    "with it, only its own outcomes are expressible. "
                    f"Only {NORMATIVE} may assert otherwise.")


def load_fixtures(directory: Path) -> list[Fixture]:
    """Load every ``*.json`` fixture in a directory, sorted by filename."""
    fixtures = []
    for path in sorted(Path(directory).glob("*.json")):
        payload = json.loads(path.read_text())
        for item in (payload if isinstance(payload, list) else [payload]):
            fixtures.append(load_fixture(item))
    return fixtures

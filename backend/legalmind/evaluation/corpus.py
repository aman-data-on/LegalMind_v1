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
``STRUCTURAL`` fixtures exercise the algorithm and are explicitly marked as
carrying no legal meaning; ``NORMATIVE`` fixtures require real material.
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
    EvidenceRef,
    EvaluatorInput,
    LegalRule,
    LiabilityFacts,
    MappingInput,
    RequirementContext,
)
from legalmind.evaluation.registry import evaluate, version_for

STRUCTURAL = "STRUCTURAL"
NORMATIVE = "NORMATIVE"


class FixtureError(Exception):
    """A fixture is malformed or omits a required assertion."""


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
    if provenance not in {STRUCTURAL, NORMATIVE}:
        raise FixtureError(
            f"{payload.get('id')}: provenance must be {STRUCTURAL} or {NORMATIVE}")

    evaluator_type = EvaluatorType(payload["evaluator_type"])
    requirement = RequirementContext(
        requirement_version_id=UUID(payload["requirement_version_id"])
        if payload.get("requirement_version_id") else uuid4(),
        code=payload["requirement_code"],
        evaluator_type=evaluator_type,
        required=bool(payload.get("required", True)))

    standard = CompanyStandard(
        version_id=uuid4(), configuration=payload.get("company_standard") or {})
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

    return Fixture(
        id=payload["id"],
        description=payload.get("description", ""),
        provenance=provenance,
        evaluator_input=EvaluatorInput(
            requirement=requirement, company_standard=standard,
            evaluator_version=version_for(evaluator_type),
            evidence=evidence, facts=facts, mapping=mapping,
            legal_rule=legal_rule),
        expect_finding_classification=FindingClassification(
            payload["expect_finding_classification"]),
        expect_evaluations=expected,
        source=payload.get("source"))


def load_fixtures(directory: Path) -> list[Fixture]:
    """Load every ``*.json`` fixture in a directory, sorted by filename."""
    fixtures = []
    for path in sorted(Path(directory).glob("*.json")):
        payload = json.loads(path.read_text())
        for item in (payload if isinstance(payload, list) else [payload]):
            fixtures.append(load_fixture(item))
    return fixtures

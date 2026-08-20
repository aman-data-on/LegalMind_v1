"""Step 45E coverage manifest — every specified fixture accounted for.

The corpus is Tier 1 and normative (54.1), so the dangerous failure is not a
fixture that fails: it is a fixture that was never written and that nobody
noticed. `corpus_coverage.json` records a status for each of the 64 ids Step 45E
specifies, and these tests make that record falsifiable — an id cannot be
dropped, invented, or claim to be AUTHORED without a fixture behind it.

They assert **coverage bookkeeping**, never a legal conclusion.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from legalmind.evaluation.corpus import (
    DOCUMENT_SUPPORTED,
    NORMATIVE,
    STANDARD_DERIVED,
    STRUCTURAL,
    TRACEABLE_PROVENANCE,
    FixtureError,
    load_fixture,
    load_fixtures,
)

CORPUS_DIR = Path(__file__).parent / "corpus"
MANIFEST_PATH = Path(__file__).parent / "corpus_coverage.json"

# Step 45E.8's own tally. A change here means the specification changed, which is
# a specification event, not a number to bump.
SPECIFIED_TOTAL = 64

STATUSES = {"AUTHORED", "AUTHORED_RATIFIED", "PARTIAL", "BLOCKED",
            "STRUCTURAL_ONLY", "SEPARATE_TRACK", "OUT_OF_V1_SCOPE",
            "UNSTARTED"}
NEEDS = {"LEGAL_RULE", "SCOPE_RULING", "SECOND_TRANCHE"}


def _manifest() -> dict[str, dict]:
    raw = json.loads(MANIFEST_PATH.read_text())
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def _specified_ids() -> set[str]:
    """The 64 ids of Step 45E, derived rather than copied from the manifest."""
    ids = {f"L-{n:02d}" for n in range(1, 29)} | {"L-29a", "L-29b"}
    ids |= {f"P-{n:02d}" for n in range(1, 7)}
    ids |= {f"R-{n:02d}" for n in range(1, 15)}
    ids |= {f"F-{n:02d}" for n in range(1, 7)}
    ids |= {f"W-{n:02d}" for n in range(1, 9)}
    return ids


def test_the_id_set_matches_45e_8s_tally():
    assert len(_specified_ids()) == SPECIFIED_TOTAL


def test_every_specified_fixture_is_accounted_for():
    """The point of the manifest: no case may be silently forgotten."""
    manifest, specified = _manifest(), _specified_ids()
    assert not specified - manifest.keys(), (
        f"unaccounted 45E fixtures: {sorted(specified - manifest.keys())}")
    assert not manifest.keys() - specified, (
        f"manifest names ids Step 45E does not specify: "
        f"{sorted(manifest.keys() - specified)}")


@pytest.mark.parametrize("fixture_id", sorted(_specified_ids()))
def test_each_entry_is_well_formed(fixture_id):
    entry = _manifest()[fixture_id]
    assert entry["status"] in STATUSES, entry
    assert set(entry.get("needs", [])) <= NEEDS, entry
    # A BLOCKED entry must say what is missing, or it is not actionable by the
    # owner. PARTIAL may omit `needs`: since 2026-08-18 a case can be partly
    # authored with the remainder being OUR unstarted work rather than anything
    # owed by the owner (L-27 is the example). Requiring `needs` there would have
    # forced a fake owner obligation into the list the owner actually reads.
    if entry["status"] == "BLOCKED":
        assert entry.get("needs"), (
            f"{fixture_id} is BLOCKED but names nothing in `needs`")
    if entry["status"] in {"AUTHORED", "AUTHORED_RATIFIED", "PARTIAL"}:
        assert entry.get("fixture"), f"{fixture_id} claims {entry['status']} " \
                                     "but names no fixture"


def test_authored_entries_name_a_fixture_that_exists():
    """Guards the failure mode where a manifest drifts from the corpus."""
    authored = {f.id for f in load_fixtures(CORPUS_DIR)}
    # Named non-corpus mechanisms are asserted elsewhere (a runner invariant, a
    # verification tool); they are listed so the reader can find them.
    external = {"run_fixture (all fixtures)", "test_runner_is_deterministic",
                "tools/verify_reproducibility.py"}
    for fixture_id, entry in _manifest().items():
        if entry["status"] not in {"AUTHORED", "AUTHORED_RATIFIED", "PARTIAL"}:
            continue
        named = {n.strip() for n in entry["fixture"].split(",")}
        unknown = named - authored - external
        assert not unknown, f"{fixture_id} names missing fixture(s): {unknown}"


def test_every_covers_entry_is_a_real_45e_id():
    """A fixture cannot claim to cover a case that does not exist."""
    specified = _specified_ids()
    for fixture in load_fixtures(CORPUS_DIR):
        unknown = set(fixture.covers) - specified
        assert not unknown, f"{fixture.id} covers unknown ids: {unknown}"


def test_fixtures_and_manifest_cannot_drift_apart():
    """Every id a real-material fixture covers must be named by that manifest entry.

    The earlier form of this test asserted that a covered id must be AUTHORED or
    PARTIAL, which was wrong: a fixture can encode a case's INPUT while the case
    stays BLOCKED. `L-01` is exactly that — DOC-LIAB-01 and STD-LIAB-02 both
    exercise MSA 17.2's six-month cap, but 45E's expected MATCH is unreachable
    because that clause measures on a different basis than the ratified standard,
    so the case still needs a six-month total-fees specimen.

    What must hold is the traceability link, in both directions: the fixture names
    the case, and the case names the fixture. That catches the drift this test
    exists for — a fixture written and the manifest never updated — without
    forcing a status the evidence does not support.
    """
    manifest = _manifest()
    for fixture in load_fixtures(CORPUS_DIR):
        if fixture.provenance not in TRACEABLE_PROVENANCE:
            continue
        for covered in fixture.covers:
            named = manifest[covered].get("fixture", "")
            assert fixture.id in named, (
                f"{fixture.id} covers {covered}, but that manifest entry does "
                f"not name it (names: {named!r})")


# ==================================================== provenance enforcement
def _document_supported_payload() -> dict:
    return json.loads(
        (CORPUS_DIR / "document_liability.json").read_text())[0]


def test_a_document_supported_fixture_may_not_carry_an_acceptance_position():
    """The owner's ruling of 2026-08-18, enforced rather than documented.

    A cap a vendor grants itself is not a standard that vendor demands. Without
    this guard, `preferred: 6` lifted from the supplied MSA would produce a MATCH
    labelled as derived from the document.
    """
    payload = _document_supported_payload()
    payload["company_standard"] = {"preferred": 6, "unit": "MONTHS"}
    with pytest.raises(FixtureError, match="must not supply company_standard"):
        load_fixture(payload)


def test_a_document_supported_fixture_may_not_carry_a_configured_tolerance():
    payload = _document_supported_payload()
    payload["legal_rule"] = {"configuration": {"acceptable_max": 12}}
    with pytest.raises(FixtureError, match="tolerance"):
        load_fixture(payload)


def test_a_document_supported_fixture_may_not_expect_match():
    payload = _document_supported_payload()
    payload["expect_evaluations"][0]["classification"] = "MATCH"
    with pytest.raises(FixtureError, match="cannot expect MATCH"):
        load_fixture(payload)


def test_a_document_supported_fixture_may_not_expect_a_rule_outcome():
    payload = _document_supported_payload()
    payload["expect_evaluations"][0]["rule_outcome"] = "ACCEPTABLE"
    with pytest.raises(FixtureError, match="Step 20 r4"):
        load_fixture(payload)


def _standard_derived_payload() -> dict:
    return json.loads((CORPUS_DIR / "standard_liability.json").read_text())[0]


def test_a_standard_derived_fixture_may_not_carry_a_configured_tolerance():
    """The owner's V1 policy: a stated position is permitted, a tolerance is not."""
    payload = _standard_derived_payload()
    payload["legal_rule"] = {"configuration": {"approval_required_above": 24}}
    with pytest.raises(FixtureError, match="acceptance policy"):
        load_fixture(payload)


def test_a_standard_derived_fixture_may_not_expect_a_rule_outcome():
    """classification is reachable at this tier; rule_outcome is not.

    This is the enforced form of "keep classification separate from rule_outcome":
    a fixture may say a clause DEVIATES from a stated position, and may not say
    that Legal must approve it.
    """
    payload = _standard_derived_payload()
    payload["expect_evaluations"][0]["rule_outcome"] = "ACCEPTABLE"
    with pytest.raises(FixtureError, match="Step 20 r4"):
        load_fixture(payload)


def test_a_standard_derived_fixture_may_expect_match():
    """The converse: MATCH must be reachable, or the tier would be pointless."""
    fixture = load_fixture(_standard_derived_payload())
    assert fixture.provenance == STANDARD_DERIVED
    assert any(x.classification.value == "MATCH"
               for x in fixture.expect_evaluations)


def test_a_standard_derived_fixture_needs_a_supplied_standard():
    payload = _document_supported_payload()
    payload["provenance"] = STANDARD_DERIVED
    with pytest.raises(FixtureError, match="but none is present"):
        load_fixture(payload)


def test_real_material_must_cite_its_source():
    """45E.7 rule 1 — otherwise a DOCUMENT_SUPPORTED label is unfalsifiable."""
    for provenance in (DOCUMENT_SUPPORTED, STANDARD_DERIVED, NORMATIVE):
        payload = _document_supported_payload()
        payload["provenance"] = provenance
        payload.pop("source_clause")
        with pytest.raises(FixtureError, match="source_document and source_clause"):
            load_fixture(payload)


def test_structural_fixtures_need_no_source():
    """Placeholder fixtures have no real source to cite, and must not invent one."""
    payload = json.loads((CORPUS_DIR / "structural_numeric.json").read_text())[0]
    assert payload["provenance"] == STRUCTURAL
    assert "source_document" not in payload
    load_fixture(payload)          # must not raise


def test_every_ratified_standard_declares_a_document_type():
    """Step 28 scoping, owner Q2/Q3 (2026-08-19): a ratified Company Standard
    file must declare which kind of paper it is the position FOR. An untyped
    standard would be unusable at publish and ambiguous as a record.
    """
    from legalmind.domain.document_types import is_document_type
    from legalmind.evaluation.corpus import RATIFIED_STANDARDS_DIR

    files = sorted(RATIFIED_STANDARDS_DIR.glob("*.json"))
    assert files, "no ratified standards found"
    for path in files:
        config = json.loads(path.read_text())["configuration"]
        declared = config.get("document_type")
        assert is_document_type(declared), (
            f"{path.name}: document_type is {declared!r}, not a locked "
            "Step 6 value")
        # The filename is the requirement code; the code should name the type
        # it scopes to, so a reader never has to open the file to know.
        assert declared.replace("_", "-") in path.stem or declared in path.stem, (
            f"{path.name}: code does not name its document type {declared}")


def test_every_ratified_standard_is_publishable_as_written():
    """Owner tasking 2026-08-19: every ratified file carries the mapping and
    extraction terminology that makes its Requirement publishable — a usable
    mapping rule set (D-1: integer confirm_threshold, no default), an
    evaluation rule payload, and for NUMERIC standards a usable extraction
    block whose bases include the ratified basis. The terms themselves are
    verified against the real source documents by tools/verify_terminology
    (which needs the gitignored documents and so cannot run here).
    """
    from legalmind.evaluation.corpus import RATIFIED_STANDARDS_DIR
    from legalmind.extraction.liability import LiabilityExtractionConfig
    from legalmind.mapping.rules import MappingRules

    for path in sorted(RATIFIED_STANDARDS_DIR.glob("*.json")):
        payload = json.loads(path.read_text())
        MappingRules.from_config(payload.get("mapping_rules"))   # raises if unusable
        assert payload.get("evaluation_rules"), (
            f"{path.name}: no evaluation_rules — the publish gate would refuse")
        assert payload.get("source_file"), (
            f"{path.name}: no source_file — verify_terminology cannot locate "
            "the document this standard cites")
        if payload.get("evaluator_type", "NUMERIC_COMPARISON") != "PRESENCE":
            config = payload["configuration"]
            extraction = LiabilityExtractionConfig.from_config(config)
            assert extraction.is_usable, (
                f"{path.name}: numeric standard with no usable extraction "
                "terminology would evaluate nothing (ENG-09)")
            assert config["basis"] in extraction.bases, (
                f"{path.name}: extraction cannot recognise the ratified basis "
                f"{config['basis']!r}, so every live evaluation would fail "
                "closed on basis comparability (45B.4)")

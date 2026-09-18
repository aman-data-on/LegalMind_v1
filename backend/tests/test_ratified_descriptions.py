"""Every ratified standard carries the owner-instructed plain-English
`description` (2026-09-09), and none of them states a number from the
standard — the value is the LEGAL-02 position, the description is served to
every reader of the Finding."""
import json
import re
from pathlib import Path

STANDARDS = sorted((Path(__file__).resolve().parents[1] / "config" / "company_standards").glob("*.json"))


def _payloads():
    return {p.stem: json.loads(p.read_text()) for p in STANDARDS}


def test_the_standard_set_is_exactly_what_the_records_ratified_and_retired():
    """Pinned on purpose: a standard enters or leaves this directory only through
    a recorded ruling. 25 ratified from LeapSwitch documents (2026-08-19/20,
    less the seven retired) + 8 approved through the Constitution L1.10
    (`AM-59` r6' and `AM-66`) + 39 approved through Constitution §31 (`AM-72`,
    AB-24, owner 2026-09-18 resolving C-23) = 72 active, + 7 retired (`AM-65`)
    = 79 files."""
    payloads = _payloads()
    retired = {c for c, d in payloads.items() if "retired" in d}
    assert len(STANDARDS) == 79
    assert len(retired) == 7, sorted(retired)
    assert len(payloads) - len(retired) == 72
    # `AM-72` — the §31 document types, by count. Pinned so a position cannot enter
    # or leave without a recorded ruling, the same discipline as the retired set.
    by_type: dict[str, int] = {}
    for d in payloads.values():
        by_type[d["configuration"]["document_type"]] = (
            by_type.get(d["configuration"]["document_type"], 0) + 1)
    assert by_type["PARTNER_AGREEMENT"] == 5      # §31.3-§31.6, §31.8, §31.4
    assert by_type["VENDOR_AGREEMENT"] == 11      # §31.9
    assert by_type["DISTRIBUTION_AGREEMENT"] == 10  # §31.10
    assert by_type["ORDER_FORM"] == 7             # §31.11
    assert by_type["AMENDMENT"] == 6              # §31.12
    # AM-65 — the seven the current Constitution does not define.
    assert retired == {
        "FORCE-MAJEURE-MSA-001", "FORCE-MAJEURE-TOS-001", "WARRANTY-DISCLAIMER-MSA-001",
        "COMPELLED-DISCLOSURE-NDA-001", "RETURN-DESTRUCTION-MSA-001",
        "RETURN-DESTRUCTION-NDA-001", "LIAB-CARVEOUTS-MSA-001"}


def test_no_generated_standard_has_drifted_from_the_constitution():
    """The §31.9-§31.12 standards are emitted from the Constitution's own words. If a
    file and its section disagree, one of them was edited by hand — and for a generated
    legal position that means a paraphrase entered the corpus (rule 7)."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "tools.generate_section31_standards", "--check"],
        cwd=STANDARDS[0].parents[2], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_retired_standard_keeps_its_record_and_says_why():
    for code, d in _payloads().items():
        if "retired" not in d:
            continue
        block = d["retired"]
        assert block["marker"] == "RETIRED — NOT PRESENT IN CURRENT CONSTITUTION", code
        assert block["reason"].strip() and block["ruling"].strip(), code
        # History is preserved, not erased: the file keeps the date it WAS
        # ratified and the document it came from (rule 17, rule 21).
        assert d["ratified"], code
        assert d["source_document"] and d["source_clause"], code
        assert d["configuration"]["constitution"]["basis"] == "RETIRED", code


def test_no_active_standard_claims_a_retired_sibling_as_evidence():
    """A retired standard must not make an active one 'expected' (AM-65)."""
    payloads = _payloads()
    retired = {c for c, d in payloads.items() if "retired" in d}
    for code, d in payloads.items():
        triggers = ((d["configuration"].get("constitution") or {}).get("expected_when") or {})
        named = set(triggers.get("confirmed_any") or [])
        assert not (named & retired), f"{code} is triggered by a retired standard: {named & retired}"


def test_every_ratified_standard_has_a_one_sentence_description():
    for path in STANDARDS:
        d = json.loads(path.read_text())
        desc = d.get("description", "")
        assert isinstance(desc, str) and 20 <= len(desc) <= 200, path.name
        assert desc.endswith("."), path.name
        assert desc.count(". ") == 0, f"{path.name}: more than one sentence"


def test_no_description_states_the_standards_value():
    for path in STANDARDS:
        d = json.loads(path.read_text())
        assert not re.search(r"\d", d["description"]), f"{path.name}: {d['description']}"


def test_no_description_pronounces_acceptability():
    for path in STANDARDS:
        d = json.loads(path.read_text())
        assert not re.search(r"\b(un)?acceptable\b|\bmust be (changed|modified)\b",
                             d["description"], re.I), path.name

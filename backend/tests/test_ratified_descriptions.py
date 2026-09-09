"""Every ratified standard carries the owner-instructed plain-English
`description` (2026-09-09), and none of them states a number from the
standard — the value is the LEGAL-02 position, the description is served to
every reader of the Finding."""
import json
import re
from pathlib import Path

STANDARDS = sorted((Path(__file__).resolve().parents[1] / "config" / "company_standards").glob("*.json"))


def test_every_ratified_standard_has_a_one_sentence_description():
    assert len(STANDARDS) == 32
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

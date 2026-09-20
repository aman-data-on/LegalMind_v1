"""The publish payload — the 33, and never the 40.

`import_ratified_standards.py` ends by printing every code it touched, all 40.
Publishing a retired code raises `BusinessRuleRejected` (`AM-65`), and one bad
code fails the whole request — so the printed list is not the list to send.

`tools.publish_payload` derives the right one from the ratified files. These
tests pin the property that actually matters: **a retired code can never reach
the payload**, however the directory changes.
"""
from __future__ import annotations

import json

import pytest

from legalmind.evaluation.corpus import RATIFIED_STANDARDS_DIR
from tools.publish_payload import EXPECT_ACTIVE, EXPECT_RETIRED, split, validate


def _write(dirpath, code, *, retired=False):
    payload = {"requirement_code": code}
    if retired:
        payload["retired"] = {"marker": "RETIRED — NOT PRESENT IN CURRENT CONSTITUTION"}
    (dirpath / f"{code}.json").write_text(json.dumps(payload))


def test_the_ratified_directory_yields_the_approved_shape():
    active, retired = split(RATIFIED_STANDARDS_DIR)
    assert len(active) == EXPECT_ACTIVE
    assert len(retired) == EXPECT_RETIRED
    assert validate(active, retired, EXPECT_ACTIVE, EXPECT_RETIRED) == []


def test_no_retired_code_is_ever_publishable():
    """The whole point. Retirement is read from the `retired` block AM-65 defines."""
    active, retired = split(RATIFIED_STANDARDS_DIR)
    assert set(active).isdisjoint(retired)
    for code in retired:
        assert code not in active


def test_a_newly_retired_standard_leaves_the_payload(tmp_path):
    _write(tmp_path, "KEEP-MSA-001")
    _write(tmp_path, "GONE-MSA-001", retired=True)
    active, retired = split(tmp_path)
    assert active == ["KEEP-MSA-001"]
    assert retired == ["GONE-MSA-001"]


def test_a_changed_count_is_refused_rather_than_emitted(tmp_path):
    """A scope change must be re-decided, not silently followed."""
    _write(tmp_path, "ONLY-MSA-001")
    active, retired = split(tmp_path)
    problems = validate(active, retired, EXPECT_ACTIVE, EXPECT_RETIRED)
    assert any("expected 72" in p for p in problems)
    assert any("expected 7" in p for p in problems)


@pytest.mark.parametrize("active,retired,expected", [
    (["A"], ["A"], "both active and retired"),
    (["A", "A"], [], "duplicate active codes"),
])
def test_overlap_and_duplicates_are_refused(active, retired, expected):
    problems = validate(active, retired, len(set(active)), len(set(retired)))
    assert any(expected in p for p in problems)

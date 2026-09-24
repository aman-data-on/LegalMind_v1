"""Roadmap PHASE 0 benchmark: the dataset stays well-formed and the scorer's taxonomy
assigns the stage that failed. No database, no model, no provider."""
import json
import re

from tools import rag_benchmark as rb

CASES = json.loads(rb.DATASET.read_text())["cases"]
REF = re.compile(r"^(POS:[A-Z0-9_-]+|CONST:[0-9.]+|STAT:[^:]+:[0-9A-Za-z*]+|POS:\*|STAT:\*)$")


def test_dataset_is_well_formed_and_covers_every_roadmap_category():
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids))
    for c in CASES:
        for ref in [r for slot in c["gold"] for r in slot] + c["must_not"]:
            assert REF.match(ref), (c["id"], ref)
        assert c["category"] in "ABCDEFGHIJKLMNO"
    counts = {k: sum(c["category"] == k for c in CASES) for k in "ABCDEFGHIJKLMNO"}
    assert min(counts.values()) >= 3, counts
    assert sum(c.get("golden", False) for c in CASES) >= 12   # roadmap §17 variants


def test_the_taxonomy_names_the_stage_that_failed():
    case = {"id": "X", "category": "E", "must_not": ["POS:LIABILITY-MSA-001"],
            "gold": [["CONST:14"], ["POS:A"], ["STAT:Indian Contract Act, 1872:74"],
                     ["POS:B"], ["POS:C"], ["POS:GONE"]]}
    shown = ["POS:X", "POS:Y", "POS:Z", "POS:C", "POS:LIABILITY-MSA-001"]
    wide = [*shown, "POS:B"]
    held = {"POS:A", "POS:B", "POS:C", "STAT:Indian Contract Act, 1872:74"}
    out = rb.score_case(case, shown, wide, {"POSITIONS"}, held.__contains__, False)
    assert [s["code"] for s in out["slots"]] == [
        "SOURCE_NOT_INDEXED", "RETRIEVAL_MISS", "ROUTE_MISSED", "RANK_CUTOFF",
        "RANK_LOW", "SOURCE_MISSING"]
    assert out["wrong_source"] == ["POS:LIABILITY-MSA-001"]


def test_statute_refs_match_by_act_prefix_and_wildcard_section():
    assert rb.ref_matches("STAT:Companies Act, 1956:*", "STAT:Companies Act, 1956 (REPEALED — x):12")
    assert not rb.ref_matches("STAT:Companies Act, 2013:*", "STAT:Companies Act, 1956 (REPEALED):12")
    assert not rb.ref_matches("STAT:Indian Contract Act, 1872:74", "STAT:Indian Contract Act, 1872:73")
    assert rb.ref_matches("POS:*", "POS:ANY")


def test_no_gold_reference_is_a_retired_standard():
    """A retired standard is never retrievable (`AM-71`), so it can never be gold —
    the PHASE 0 verification checked that chunks existed, not that the standard was
    active, and six cases carried one until 2026-09-25 (`AM-65`'s seven)."""
    retired = {"COMPELLED-DISCLOSURE-NDA-001", "FORCE-MAJEURE-MSA-001",
               "FORCE-MAJEURE-TOS-001", "LIAB-CARVEOUTS-MSA-001",
               "RETURN-DESTRUCTION-MSA-001", "RETURN-DESTRUCTION-NDA-001",
               "WARRANTY-DISCLAIMER-MSA-001"}
    for c in CASES:
        for ref in (r for slot in c["gold"] for r in slot):
            assert ref.removeprefix("POS:") not in retired, (c["id"], ref)

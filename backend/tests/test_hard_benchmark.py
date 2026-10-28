"""The hard Ask retrieval benchmark: the owner-approved set stays well-formed, and the
scorer ranks within a source kind, reads wildcards and catches the other brand. No
database, no model, no provider."""
import json
import re

from tools import hard_benchmark as hb

CASES = json.loads(hb.DATASET.read_text())["cases"]
REF = re.compile(r"^(CONST|POS|STAT|PUB):\S")


def test_the_set_is_well_formed():
    assert len(CASES) == 50 and len({c["id"] for c in CASES}) == 50
    for c in CASES:
        assert c["cat"] in {"paraphrase", "hinglish", "email", "missing", "conflict",
                            "brand", "multihop"}, c["id"]
        for ref in [r for slot in c["gold"] for r in slot] + c.get("must_not", []):
            assert REF.match(ref), (c["id"], ref)
    assert all(c.get("must_not") for c in CASES if c["cat"] == "brand")


def test_a_ref_meets_its_sub_sections_and_a_statute_its_full_title():
    assert hb.matches("CONST:9", "CONST:9.2") and not hb.matches("CONST:9", "CONST:19")
    assert hb.matches("STAT:CERT-In Directions*", "STAT:CERT-In Directions under (6):ii")
    assert hb.matches("STAT:Indian Contract Act, 1872:74",
                      "STAT:Indian Contract Act, 1872 (as amended):74")
    assert not hb.matches("STAT:Indian Contract Act, 1872:74",
                          "STAT:Indian Contract Act, 1872:73")
    assert hb.matches("PUB:PUBLISHED_TOS_*:*Late Fees", "PUB:PUBLISHED_TOS_LEAPSWITCH:7. Late Fees")


def test_a_statute_shown_after_other_sources_still_ranks_first_in_its_kind():
    case = {"id": "S", "cat": "multihop", "gold": [["CONST:14"], ["STAT:Indian Contract Act, 1872:74"]]}
    shown = ["CONST:30", "CONST:14", "CONST:31", "POS:A", "POS:B", "STAT:Indian Contract Act, 1872:74"]
    assert hb.score(case, shown)["ranks"] == [2, 1]


def test_the_other_brand_shown_counts_and_a_regression_fails_the_run():
    case = {"id": "B", "cat": "brand", "gold": [["PUB:PUBLISHED_SLA_CLOUDPE:*"]],
            "must_not": ["PUB:PUBLISHED_SLA_LEAPSWITCH:*"]}
    row = hb.score(case, ["PUB:PUBLISHED_SLA_CLOUDPE:Credits", "PUB:PUBLISHED_SLA_LEAPSWITCH:Credits"])
    assert row["ranks"] == [1] and row["wrong_brand"] is True
    base = {"overall": {"recall@3": 0.9, "wrong_brand": 0.0, "cases": 50}}
    now = {"overall": {"recall@3": 0.9, "wrong_brand": 0.2, "cases": 50}}
    assert hb.regressions(now, base) == ["wrong_brand 0.0 -> 0.2"]
    assert hb.regressions(base, base) == []

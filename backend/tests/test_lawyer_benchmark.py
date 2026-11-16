"""R2 S1 — the lawyer-review benchmark's scorer, on a synthetic gold (rule 21: the real
review lives only in legal-docs/ and is never copied here)."""
from __future__ import annotations

import json

from tools import lawyer_benchmark as B

GOLD = """# synthetic
1 | 4.4, 4.4.1-4.4.2 x | deleted | 4.4 REJECT (keep). 4.4.1 ACCEPT WITH CHANGES: y.
2 | 8.3 window | longer | ACCEPT WITH CHANGES: 15 days.
3 | 17.1; 17.6 duplicate | x | 17.1(a) ACCEPT WITH CHANGES: z. 17.6 REJECT: keep.
not a row | 9 | x | REJECT
"""


def test_gold_rows_and_refs():
    rows = B.parse_gold(GOLD)
    assert [(r["sr"], r["reject"]) for r in rows] == [(1, True), (2, False), (3, True)]
    assert rows[0]["clauses"] == ["4.4", "4.4.1", "4.4.2"]
    assert rows[2]["clauses"] == ["17.1", "17.6"]


def test_score_touch_rules_and_noise_by_origin():
    gold = B.parse_gold(GOLD)
    points = B.load_points({"points": [
        {"clauses": ["4.4.2"], "origin": "CLIENT_CHANGED"},   # row 1
        {"clauses": ["17"]},                                  # a bare section: no row
        {"clauses": ["12.3"], "origin": "ALREADY_OURS"}]})    # noise, ours
    got = B.score(gold, points)
    assert (got["rows_touched"], got["reject_rows_touched"], got["reject_rows"]) == (1, 1, 2)
    assert got["noise_by_origin"] == {"unlabelled": 1, "ALREADY_OURS": 1}
    assert got["missed_reject_rows"] == [3]


def test_an_engine_run_skips_match_points():
    run = {"A": {"classification": "MATCH", "cited": [["8.3", 1]]},
           "B": {"classification": "DEVIATION", "cited": [["8.3", 1]]}}
    assert B.load_points(run) == [{"code": "B", "clauses": ["8.3"]}]


def test_without_the_review_it_says_skipped(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LEGALMIND_SOURCE_MATERIAL_DIR", str(tmp_path))
    points = tmp_path / "p.json"
    points.write_text(json.dumps({"points": []}))
    assert B.main(["--points", str(points)]) == 0
    assert capsys.readouterr().out.startswith("SKIPPED")


def test_a_change_listing_counts_auto_accepts_and_flags_one_on_a_reject_row():
    """Priyen's rule (2026-11-16): an automatic acceptance on a row the lawyer
    REJECTED is a false auto-accept, listed."""
    listing = {"changes": [
        {"clause": {"number": "4.4.1"}, "effect_for_us": "POSITIVE",
         "answer": {"auto": True}},                                   # row 1: REJECT row
        {"clause": {"number": "8.3"}, "effect_for_us": "NEUTRAL",
         "answer": {"auto": True}},                                   # row 2: no REJECT
        {"clause": {"number": "17.6"}, "effect_for_us": "NEGATIVE", "answer": None}]}
    got = B.score(B.parse_gold(GOLD), B.load_points(listing))
    assert (got["auto_accepted"], got["to_legal"]) == (2, 1)
    assert [p["reject_rows"] for p in got["auto_on_reject_rows"]] == [[1]]

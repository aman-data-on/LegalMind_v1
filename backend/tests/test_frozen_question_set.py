"""The 77-question retrieval set is FROZEN as q77-v1 (owner, 2026-10-01, Phase 2 A1).

Every retrieval comparison between `main` and a branch is made on this exact file. An
edit — even an added field — makes two runs incomparable (the Phase 1 "0.922 vs
0.891" was), so it must arrive as a new version with a new recorded hash, never in
place. This test is what turns that rule into a property.
"""
import hashlib
import json
import pathlib

FROZEN = {"version": "q77-v1",
          "sha256": "c06162de020d8761e7ae02d056bb172f8751caf94d1ce9e6cf4d4f1f970a8b92",
          "questions": 77}
DATASET = pathlib.Path(__file__).parent / "assist_eval" / "questions_draft.json"


def test_the_77_question_set_is_byte_identical_to_its_frozen_version():
    data = DATASET.read_bytes()
    assert hashlib.sha256(data).hexdigest() == FROZEN["sha256"], (
        f"{DATASET.name} changed: record a new version and hash; never edit {FROZEN['version']}")
    assert len(json.loads(data)["questions"]) == FROZEN["questions"]

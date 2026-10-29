"""AM-224 — what each client change does to LeapSwitch. Synthetic shapes only (54.6),
each modelled on a shape a client's marked-up MSA carried; recorded model outputs, every
adversarial one dropped by code."""
from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

from legalmind.analysis import change_triage as T
from legalmind.analysis.client_changes import client_changes
from legalmind.mapping.engine import Clause
from tests.test_analysis import build, storage  # noqa: F401 — fixtures


def _reasons(before: str, after: str) -> list[str]:
    return [r["reason"] for r in T.code_reading(before, after)["reasons"]]


def test_each_sentence_the_client_added_or_removed_is_read_for_whom_it_binds():
    assert _reasons("", "LeapSwitch shall provide transition assistance for 90 days.") == \
        ["Adds a duty on LeapSwitch"]
    assert _reasons("", "The Customer may terminate for convenience on 30 days' notice.") \
        == ["Gives the client a new right"]
    assert _reasons("", "The Customer shall not be required to pay for unavailable "
                        "Services.") == ["Limits or excuses the client's liability"]
    assert _reasons("LeapSwitch reserves the right to reject any Purchase Order.", "") == \
        ["Removes a right of LeapSwitch"]
    assert _reasons("LeapSwitch shall be exempted from performance without any "
                    "liability.", "") == ["Removes a protection of LeapSwitch"]
    assert _reasons("The Customer shall pay 200% of the monthly charges for overstay.",
                    "") == ["Removes a duty of the client"]


def test_a_rewritten_sentence_is_never_a_removal_plus_an_addition():
    """10 → 30 days: who gains depends on meaning, which code never guesses."""
    read = T.code_reading("The Customer shall inform LeapSwitch at least 10 days before.",
                          "The Customer shall inform LeapSwitch at least 30 days before.")
    assert read["reasons"] == [] and read["helps"] is False and not read["editorial"]


def test_code_never_says_a_change_helps_us():
    """Measured on a real MSA: code's "helps us" was right 1 time in 4 — kept only as
    agreement with the model, never shown alone."""
    read = T.code_reading("LeapSwitch shall notify the Customer after suspension.", "")
    assert read["reasons"] == [] and read["helps"] is True
    assert T.merged(read, None, [])["effect"] is None


def test_a_wording_only_change_is_editorial():
    assert T.code_reading("The Parties shall comply, with law.",
                          "The parties shall comply with law")["editorial"]


def test_the_topic_is_named_by_the_heading_in_the_constitutions_own_titles():
    assert T.topics_for_heading("TERM AND TERMINATION") == ["13", "14"]
    assert T.topics_for_heading("LIMITATION OF LIABILITY") == ["9"]
    assert T.topics_for_heading("GOVERNING LAW AND ARBITRATION") == ["22"]
    assert T.topics_for_heading("SCOPE OF SERVICES") == []      # "services" names none
    assert T.topics_for_heading(None) == []


def test_every_playbook_topic_carries_its_own_words():
    book = T.playbook()
    assert set(book) == {str(n) for n in range(9, 23)}
    assert book["9"]["position"].startswith("Company Position")
    assert book["14"]["position"].startswith("No early exit is permitted")  # "(Established)"


CHANGES = [{"evidence_id": "e1", "clause": "7.2", "before": "",
            "after": "The Customer may terminate for convenience on 30 days' notice.",
            "changed": ["The Customer may terminate for convenience on 30 days' notice."]},
           {"evidence_id": "e2", "clause": "8.6",
            "before": "The Customer shall inform LeapSwitch 10 days before.",
            "after": "The Customer shall inform LeapSwitch 30 days before.",
            "changed": ["The Customer shall inform LeapSwitch 10 days before.",
                        "The Customer shall inform LeapSwitch 30 days before."]}]


def test_only_a_known_effect_a_real_topic_and_a_quote_of_the_changed_words_are_kept():
    raw = json.dumps({"1": {"effect": T.WORSE, "topic": "14",
                            "quote": "may terminate for convenience"},
                      "2": {"effect": T.BETTER, "topic": "NONE",
                            "quote": "shall inform LeapSwitch 30 days before"}})
    kept = T.verify(raw, CHANGES)
    assert [(k["evidence_id"], k["effect"], k["topic"]) for k in kept] == [
        ("e1", T.ONTO, "14"), ("e2", T.AWAY, None)]


def test_every_adversarial_output_is_dropped():
    raw = json.dumps({
        "1": {"effect": T.WORSE, "topic": "14", "quote": "the Customer has unlimited rights"},
        "2": {"effect": "ACCEPTABLE", "topic": "16",
              "quote": "shall inform LeapSwitch 30 days before"},
        "3": {"effect": T.WORSE, "topic": "9", "quote": "may terminate for convenience"},
        "0": {"effect": T.WORSE, "topic": "9", "quote": "may terminate for convenience"}})
    bad_topic = json.dumps({"1": {"effect": T.WORSE, "topic": "31",
                                  "quote": "may terminate for convenience"}})
    short = json.dumps({"1": {"effect": T.WORSE, "topic": "14", "quote": "may"}})
    assert T.verify(raw, CHANGES) == [] and T.verify(bad_topic, CHANGES) == []
    assert T.verify(short, CHANGES) == [] and T.verify("not json", CHANGES) == []


def test_away_from_us_only_when_code_and_the_model_agree():
    helps = T.code_reading("LeapSwitch shall notify the Customer after suspension.", "")
    silent = T.code_reading("Within 10 days.", "Within 30 days.")
    onto = T.code_reading("", "LeapSwitch shall indemnify the Customer.")
    away = {"effect": T.AWAY, "topic": None, "quote": "q"}
    assert T.merged(helps, away, [])["effect"] == T.AWAY
    assert T.merged(silent, away, [])["effect"] is None
    assert T.merged(onto, away, [])["effect"] == T.ONTO     # code's reason stands
    assert T.merged(silent, {**away, "effect": T.ONTO}, [])["effect"] == T.ONTO
    shown = T.merged(silent, {**away, "effect": T.ONTO}, ["13"])
    assert shown["reading"]["label"] == T.LABEL and shown["topics"][0]["section"] == "13"


def _marked(before: str, after: str, number: str = "7.2") -> list[Clause]:
    return [Clause(evidence_id=uuid4(), content="Term and Termination", section_number="7",
                   section_title="TERM AND TERMINATION"),
            Clause(evidence_id=uuid4(), content=after, section_number=number,
                   marks={"changes": [{"deleted": before, "inserted": after}],
                          "comments": [], "original": before})]


def test_our_position_is_omitted_for_a_reader_not_permitted_to_see_it():
    rows = _marked("The Customer shall have no right to terminate before the Term ends.",
                   "The Customer may terminate for convenience on 30 days' notice.")
    seen = client_changes(rows, {}, legal_position=True)
    hidden = client_changes(rows, {}, legal_position=False)
    assert seen["onto"] == hidden["onto"] == 1
    assert all(t["position"] for t in seen["sections"][0]["clauses"][0]["topics"])
    assert all("position" not in t for t in hidden["sections"][0]["clauses"][0]["topics"])


def test_the_model_is_asked_once_per_text_prompt_and_model(build, db):
    review = build.review(["7. Term", "The Customer may terminate on 30 days' notice."])
    rows = _marked("The Customer shall have no right to terminate before the Term ends.",
                   "The Customer may terminate for convenience on 30 days' notice.")
    asked = []

    def ask(prompt, version):
        asked.append(version)
        return SimpleNamespace(text=json.dumps({"1": {
            "effect": T.WORSE, "topic": "14", "quote": "may terminate for convenience"}}),
            model="m")
    first = T.run(db, review.document_version_id, rows, "MSA", ask, "m")
    again = T.run(db, review.document_version_id, rows, "MSA", ask, "m")
    assert asked == [T.PROMPT_VERSION] and first == again and len(first) == 1
    assert T.run(db, review.document_version_id, rows, "MSA",
                 lambda p, v: None, "other-model") is None        # no model: nothing
    assert T.read_back(db, review.document_version_id)[str(rows[1].evidence_id)][
        "topic"] == "14"

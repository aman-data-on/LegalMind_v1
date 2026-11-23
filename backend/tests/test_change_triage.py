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


def test_a_title_half_with_a_short_word_needs_all_its_words():
    """Batch 6 (AM-224 r3): "governing" alone named §22 Governing Law; "SLA" (three
    letters) named nothing. A half holding a short word needs every word; "laws" reads
    "law"."""
    assert T.topics_for_heading("TERMS GOVERNING THE SERVICES") == []
    assert T.topics_for_heading("GOVERNING LAW AND JURISDICTION") == ["22"]
    assert T.topics_for_heading("GOVERNING LAWS") == ["22"]
    assert T.topics_for_heading("Hardware SLA") == ["11"]
    assert T.topics_for_heading("DATA PROCESSING") == ["12"]
    assert T.topics_for_heading("TERM AND TERMINATION") == ["13", "14"]


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


# ------------------------------------------------- batch 6 (2026-11-20): F1–F4, AM-224 r1
NONE: tuple[list[str], list[str]] = ([], [])


def test_a_role_either_party_holds_binds_both():
    """F1: "the Receiving Party", "Neither Party" are no one's alone — MUTUAL, which has
    no reason of its own (a mutual change is Legal's to weigh). A one-way paper whose
    parties block binds the role to one side keeps that side."""
    assert T._who("The Receiving Party shall return all Confidential Information within "
                  "ten days of a written request.", False, NONE) == "MUTUAL"
    assert T._who("Neither Party may assign this Agreement without consent.", False,
                  NONE) == "MUTUAL"
    assert T._who("The Disclosing Party may require the return of its information.",
                  False, (["disclosing party"], ["receiving party"])) == "OUR_RIGHT"
    assert _reasons("", "Neither Party may assign this Agreement without consent.") == []


def test_a_list_item_is_read_after_its_parents_lead_in():
    """F2: "any breach … by the Buyer;" names its actor in the lead-in only."""
    lead = T.lead_in("12.2 The Buyer shall indemnify the Provider against claims "
                     "arising from:")
    item = "12.2.3. any breach of the acceptable use policy by the Buyer;"
    assert [r["reason"] for r in T.code_reading(item, "", lead=lead)["reasons"]] == \
        ["Removes a duty of the client"]
    assert _reasons(item, "") == []
    assert T.lead_in("12.2 The Buyer shall indemnify the Provider.") is None
    assert (T.parent_number("12.2.3"), T.parent_number("12"), T.parent_number(None)) \
        == ("12.2", None, None)


def test_a_pronoun_acts_for_the_one_party_named_before_it():
    """F3: "If the Customer …, it shall …" — never when two sides are named before it."""
    assert _reasons("If the Customer does not collect its hardware within ten days, it "
                    "shall be liable to pay a storage fee of 150% of the monthly charge.",
                    "") == ["Removes a duty of the client"]
    assert T._who("If the Customer notifies LeapSwitch of a fault in writing, it shall "
                  "respond.", False, NONE) is None


def test_a_definition_never_reads_as_helping_us():
    """F4: removing "X's Confidential Information shall include …" is no duty of ours
    taken away; its reasons (none here) are unchanged."""
    read = T.code_reading("The Provider's Confidential Information shall include its "
                          "rate cards and roadmaps.", "")
    assert read["helps"] is False and read["reasons"] == []
    assert T.code_reading("LeapSwitch shall provide transition assistance.", "")[
        "helps"] is True                                   # a real duty still does


def test_precedence_stays_the_models_to_read():
    """RC4 (AM-224 r6): no party acts — code says nothing."""
    assert _reasons("", "The signed order form prevails over any online policy.") == []


# ------------------------------------------------ batch 6 round 2 (independent verifier)
def test_a_named_party_acting_later_wins_over_a_role():
    """D2: a role or "neither party" binds both only when no party the paper names acts
    in the sentence — the duty the client named loses no reason."""
    assert _reasons("The Disclosing Party may request return of its information, and the "
                    "Customer shall comply within ten days.", "") == \
        ["Removes a duty of the client"]
    assert _reasons("Neither Party shall be liable for indirect loss, provided that the "
                    "Customer shall pay all fees due.", "") == ["Removes a duty of the client"]


def test_a_lead_in_or_a_pronoun_never_says_a_change_helps_us():
    """D3: an exception removed from OUR indemnity is read after its lead-in for a reason
    only — never as "helps us"; a pronoun is a party only bearing what a party bears."""
    lead = ("16.2 LeapSwitch shall indemnify the Customer against third-party claims, "
            "except claims arising from:")
    read = T.code_reading("16.2.1. any modification of the Services by the Customer;", "",
                          lead=lead)
    assert read["helps"] is False and read["reasons"] == []
    for added in ("If LeapSwitch suspends the Services, it shall remain suspended until "
                  "all overdue amounts are paid.",
                  "If the Customer places an order, it shall state the service plan.",
                  "If the Customer terminates early, its liability shall not exceed the "
                  "fees paid."):
        assert _reasons("", added) == [], added


def test_only_a_defining_sentence_is_a_definition():
    """D10: "X includes …" before any other verb defines; "LeapSwitch shall ensure the
    service includes …" is a duty, and taking it away still helps the client's reading."""
    assert T.code_reading("LeapSwitch's Confidential Information includes its pricing.",
                          "")["helps"] is False
    assert T.code_reading("LeapSwitch shall ensure the service includes daily backups.",
                          "")["helps"] is True


def test_a_named_party_in_a_condition_after_each_party_is_no_actor():
    """R2-1: after "Either/Each/Neither Party" acts, a named party wins only with a duty
    or right of its own; the subject of a condition ("… while LeapSwitch is
    investigating", "… if LeapSwitch is acquired") reads as origin/main reads it, and
    `helps` keeps origin/main's order (the first party that acts)."""
    read = T.code_reading("Either Party may suspend performance while LeapSwitch is "
                          "investigating a security incident.", "")
    assert read["helps"] is False and read["reasons"] == []
    assert _reasons("", "Either Party may terminate this Agreement if LeapSwitch is "
                        "acquired by a competitor.") == []
    assert _reasons("Each Party may terminate on notice if the Customer has not paid for "
                    "sixty days.", "") == []


# ---------------------------------------------- batch 8 R4 (AM-466): a rewrite's structure
def _risks(before: str, after: str, floor: tuple[str, ...] = ()) -> list[str]:
    read = T.code_reading(before, after, floor=floor)
    assert read["reasons"] == []        # never a sentence reason: the route cannot move
    return [r["reason"] for r in read["risks"]]


_CAP = ("Liability is capped at the fees paid in the last 12 months, provided that the cap "
        "shall not apply to liability arising from fraud, breach of confidentiality, or "
        "infringement of intellectual property rights.")


def test_a_new_class_taken_out_of_the_cap_moves_risk_onto_us():
    grown = _CAP.replace("confidentiality,", "confidentiality, including any security "
                                             "incident affecting the Customer's data,")
    assert _risks(_CAP, grown) == [T.RISK_CAP]
    read = T.code_reading(_CAP, grown)
    assert read["risks"][0]["quote"].startswith("including any security incident")
    assert T.merged(read, None, [])["effect"] == T.ONTO
    # a class only reworded ("rights" → "right") is no new class
    assert _risks(_CAP, _CAP.replace("rights.", "right.")) == []


def test_a_lawful_floor_item_added_to_the_carve_out_is_silent():
    grown = _CAP.replace("fraud,", "fraud, death or personal injury caused by negligence,")
    assert _risks(_CAP, grown, floor=("death or personal injury caused by negligence",)) == []
    assert _risks(_CAP, grown) == [T.RISK_CAP]          # no floor: it counts


def test_a_customer_only_carve_out_growing_is_silent():
    old = ("The limitation of liability shall not apply to the Customer's payment "
           "obligations.")
    new = ("The limitation of liability shall not apply to the Customer's payment "
           "obligations or the Customer's indemnity obligations.")
    assert _risks(old, new) == []                                          # AM-388


_INDEMNITY = ("LeapSwitch shall indemnify the Customer against third-party claims arising "
              "from breach of applicable laws, breach of confidentiality, or any failure "
              "of the Services.")


def test_a_list_item_added_to_our_indemnity_widens_our_duty():
    grown = _INDEMNITY.replace("confidentiality,", "confidentiality, any loss of the "
                                                   "Customer's data,")
    read = T.code_reading(_INDEMNITY, grown)
    assert [r["reason"] for r in read["risks"]] == [T.RISK_DUTY]
    assert read["risks"][0]["quote"] == "any loss of the Customer's data"


def test_an_except_clause_added_to_our_duty_is_silent():
    for words in ("except any claim caused by the Customer", "only to the extent caused by it"):
        grown = _INDEMNITY.replace("confidentiality,", f"confidentiality, {words},")
        assert _risks(_INDEMNITY, grown) == []
    # a word replaced, not only inserted: a person reads it
    assert _risks(_INDEMNITY, _INDEMNITY.replace("applicable laws", "any laws")) == []


def test_an_item_added_to_an_exception_list_is_silent():
    """D2: "… except to its employees, contractors and advisors" — one more person the
    duty does not reach narrows it; the narrowing word sits earlier in the sentence."""
    old = ("LeapSwitch shall keep the Customer's information confidential, except for "
           "disclosure to its employees, contractors and advisors.")
    grown = old.replace("contractors and", "contractors, auditors and")
    assert _risks(old, grown) == []


def test_an_item_added_to_a_prohibition_is_silent():
    old = "LeapSwitch shall not disclose the Customer's data to its affiliates or vendors."
    assert _risks(old, old.replace("affiliates or", "affiliates, auditors or")) == []


def test_an_item_added_to_a_positive_duty_still_widens_it():
    old = ("LeapSwitch shall indemnify the Customer against claims arising from breach of "
           "law, breach of confidentiality, or any failure of the Services.")
    grown = old.replace("confidentiality,", "confidentiality, any data breach,")
    assert _risks(old, grown) == [T.RISK_DUTY]


def test_our_notice_period_shortened_gives_us_less_time():
    old = "LeapSwitch shall notify the Customer of any breach within 24 hours of discovery."
    assert _risks(old, old.replace("24 hours", "4 hours")) == [
        "Gives LeapSwitch less time: 24 hours → 4 hours"]
    assert _risks(old, old.replace("24 hours", "48 hours")) == []      # never "helps us"


def test_the_clients_payment_period_lengthened_gives_them_more_time():
    old = "The Customer shall pay all fees within 21 days of the invoice date."
    assert _risks(old, old.replace("21 days", "30 days")) == [
        "Gives the client more time: 21 days → 30 days"]
    # a minimum notice is no deadline: a longer one binds the one who gives it
    notice = "The Customer shall give at least 30 days' notice of termination."
    assert _risks(notice, notice.replace("30", "60")) == []


def test_mixed_units_say_nothing():
    old = "LeapSwitch shall restore the Services within 2 days of the report."
    assert _risks(old, old.replace("2 days", "4 hours")) == []
    two = "LeapSwitch shall respond within 2 hours and resolve within 8 hours."
    assert _risks(two, two.replace("2 hours", "1 hours")) == []        # several figures


def test_thirty_in_parentheses_is_read():
    old = "The Customer shall pay all fees within fifteen (15) days of the invoice date."
    assert _risks(old, old.replace("fifteen (15)", "thirty (30)")) == [
        "Gives the client more time: 15 days → 30 days"]


def test_party_as_noun_modifier_is_not_the_actor():
    # "Customer data shall be …" — the Customer does not act; the AM-224 reading is
    # unchanged (THEIR_DUTY), the structural reading sees through it
    s = "Any breach affecting Customer data shall be reported promptly."
    assert T._first_actor(s, False, ([], [])) == "THEIR_DUTY"
    assert T._binder(s, False, ([], [])) is None


def test_passive_to_the_customer_binds_leapswitch():
    old = ("Any security breach affecting Customer data shall be notified to the Customer "
           "within 24 hours of discovery.")
    assert T._binder(old, False, ([], [])) == "OUR_DUTY"
    assert _risks(old, old.replace("24 hours", "4 hours")) == [
        "Gives LeapSwitch less time: 24 hours → 4 hours"]
    assert T._binder("Invoices shall be paid to LeapSwitch within 21 days.", False,
                     ([], [])) == "THEIR_DUTY"

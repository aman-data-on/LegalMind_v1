"""P1 claim set — the generator makes exactly the meaning change it names, refuses one
it cannot make cleanly, and the scorer counts exactly. No DB, no model, no network.

The sentences below are public statute text (Indian Contract Act 1872, Arbitration and
Conciliation Act 1996) or neutral drafting shapes; nothing here is a company position.
"""
from __future__ import annotations

from tools import eval_claims as ec

ARB = ("The arbitral tribunal may correct any error of the type referred to in clause (a) "
       "of sub-section (1), on its own initiative, within thirty days from the date of the "
       "arbitral award.")


def made(sentence: str, evidence: str = "") -> dict[str, list[tuple[str, str]]]:
    out: dict[str, list[tuple[str, str]]] = {}
    for cls, op, text in ec.perturb(sentence, evidence or sentence)[0]:
        out.setdefault(cls, []).append((op, text))
    return out


def test_statement_strips_marginal_note_numbering_and_footnote():
    s = "12. Protection of action taken in good faith.—(1) No suit shall lie against " \
        "the Board for anything done in good faith under this Act. 2."
    assert ec.statement(s) == ("No suit shall lie against the Board for anything done in "
                               "good faith under this Act.")
    assert ec.statement("Right to Erasure: You may request erasure of your data.") \
        == "You may request erasure of your data."


def test_faithful_restatements_keep_the_words_that_carry_meaning():
    got = dict(ec.faithful("The Customer shall pay the invoice prior to the due date.",
                           "Under the agreement,"))
    assert got["attributed"] == ("Under the agreement, the Customer shall pay the invoice "
                                 "prior to the due date.")
    assert got["reworded"] == "The Customer must pay the invoice before the due date."
    # "shall mean" is a definition, never an obligation — not reworded to "must"
    assert "reworded" not in dict(ec.faithful('"Fees" shall mean the charges payable.',
                                              "Under the agreement,"))


def test_each_class_changes_meaning_in_the_named_way():
    m = made(ARB)
    assert ("may_must", ARB.replace("may correct", "must correct")) in m["OVERSTATED"]
    assert ("insert_not", ARB.replace("may correct", "may not correct")) in m["REVERSED"]
    assert ("figure", ARB.replace("thirty days", "61 days")) in m["NUMBER_CHANGED"]
    assert ("unit", ARB.replace("thirty days", "thirty months")) in m["NUMBER_CHANGED"]
    assert "CONDITION_DROPPED" not in m           # no separable condition: skipped
    for cls, rows in m.items():
        for _, text in rows:
            assert text != ec.statement(ARB), cls


def test_reversal_removes_an_existing_negation_instead_of_stacking_one():
    m = made("A company shall not issue shares at a discount except as provided in this "
             "section.")
    assert m["REVERSED"][0] == ("drop_not", "A company shall issue shares at a discount "
                                            "except as provided in this section.")
    assert m["EXCEPTION_OMITTED"] == [("tail_exception",
                                       "A company shall not issue shares at a discount.")]


def test_condition_drop_only_where_the_rest_is_a_whole_clause():
    m = made("If the drawee cannot be found after reasonable search, the holder may treat "
             "the bill as dishonoured.")
    assert m["CONDITION_DROPPED"] == [("lead_condition",
                                       "The holder may treat the bill as dishonoured.")]
    # cut inside a relative clause, or a limb that takes the main verb: refused
    refused = ("When the holder enters into any contract which, under section 134 of the "
               "Act, would discharge the parties, the holder may reserve his right.")
    assert "CONDITION_DROPPED" not in made(refused)
    garbage = ("Whoever abets any offence shall, if the act abetted is committed, and no "
               "express provision is made, be punished.")
    assert "CONDITION_DROPPED" not in made(garbage)
    relative = "It shall also apply to awards made in the State where enforcement is sought."
    assert "CONDITION_DROPPED" not in made(relative)


def test_scope_widening_replaces_the_named_party_and_respects_mutual_clauses():
    m = made("The Customer shall notify the provider within thirty days of any change.")
    assert ("party_to_each_party", "Each party shall notify the provider within thirty "
                                   "days of any change.") in m["SCOPE_WIDENED"]
    assert "SCOPE_WIDENED" not in made("Each party shall keep the terms confidential at "
                                       "all times during the term.")


def test_unsupported_conclusion_never_restates_something_the_evidence_says():
    s = "The Customer shall pay all undisputed invoices within thirty days of receipt."
    concl = made(s, s + " Either party may terminate on notice.")["UNSUPPORTED_CONCLUSION"]
    assert "terminate" not in concl[0][1]
    every = s + " terminate void enforce compensation damages imprisonment offence"
    assert "UNSUPPORTED_CONCLUSION" not in made(s, every)


def test_tags_mark_the_hard_shapes():
    assert ec.tags(ARB, []) == []
    assert "modal_far" in ec.tags("The Customer shall, within thirty days of receipt, pay "
                                  "the invoice.", [])
    assert "double_negative" in ec.tags("No party shall be liable unless notice is not "
                                        "given in time.", [])
    assert set(ec.tags(ARB, ["xref", "definition"])) == {"cross_reference", "defined_term"}


def test_counterparty_names_are_found_and_redacted_but_ours_are_kept():
    pre = ("This Agreement is made BETWEEN Acme Widgets Pvt. Ltd, a company incorporated "
           "under the Companies Act, 2013\nAND LeapSwitch Networks Pvt Ltd.")
    names = ec.counterparty_names(pre)
    assert "Acme Widgets" in names and not any("LeapSwitch" in n for n in names)
    assert ec.redact("Acme Widgets shall pay LeapSwitch.", names) \
        == "[COUNTERPARTY] shall pay LeapSwitch."


def test_definitions_and_cross_references_are_attached_as_evidence():
    unit = ec.Unit("doc", "contract", "cl3", "Clause 3",
                   "Subject to Clause 7.2, the Customer shall pay the Fees.", "CONTRACT",
                   "CONTRACT", "Under the agreement,")
    defs = ec.definitions('"Fees" means the charges set out in the order form.')
    ec.attach(unit, defs, {"7.2": "No Fees are payable during a suspension."}.get)
    assert [role for role, _ in unit.context] == ["definition", "xref"]


def test_items_for_dedupes_across_splits_and_keeps_one_class_per_item():
    text = ("The Customer may terminate this Agreement on thirty days written notice. "
            "Each party shall keep the terms confidential at all times.")
    unit = ec.Unit("d1", "contract", "cl1", "Clause 1", text, "CONTRACT", "CONTRACT",
                   "Under the agreement,")
    seen: set[str] = set()
    items, _ = ec.items_for([unit], "dev", 10, seen)
    again, _ = ec.items_for([unit], "unseen", 10, seen)
    assert items and not again
    assert {i["label"] for i in items} <= set(ec.CLASSES)
    assert len({i["id"] for i in items}) == len(items)
    assert all(i["evidence"][0]["role"] == "clause" for i in items)


def test_score_counts_exactly_and_lists_every_failure():
    def item(label, tags=()):
        return {"id": label, "label": label, "op": "x", "claim": label, "doc": "d",
                "unit": "u", "family": "statute", "tags": list(tags)}
    items = [item("FAITHFUL"), item("FAITHFUL"), item("REVERSED", ["double_negative"]),
             item("OVERSTATED")]
    accept = {"FAITHFUL": False, "REVERSED": True, "OVERSTATED": False}
    res = ec.score(items, lambda it: accept[it["label"]])
    assert res["all"]["FAITHFUL"] == {"accepted": 0, "n": 2, "rejected": 2,
                                      "abstained": 0}
    assert res["all"]["REVERSED"] == {"accepted": 1, "n": 1, "abstained": 0}
    assert res["all"]["OVERSTATED"] == {"accepted": 0, "n": 1, "abstained": 0}
    assert res["adversarial"]["REVERSED"] == {"accepted": 1, "n": 1, "abstained": 0}
    assert sorted(f["class"] for f in res["failures"]) == ["FAITHFUL", "FAITHFUL",
                                                           "REVERSED"]
    md = ec.markdown({"dev": res}, "stub")
    assert "| reversed accepted | 1/1 | 1/1 |" in md
    assert "| faithful falsely rejected | 2/2 | — |" in md
    assert "Abstained" not in md


def test_an_abstention_is_counted_apart_never_as_an_acceptance_or_a_rejection():
    def item(label):
        return {"id": label, "label": label, "op": "x", "claim": label, "doc": "d",
                "unit": "u", "family": "statute", "tags": []}
    items = [item("FAITHFUL"), item("FAITHFUL"), item("FAITHFUL"),
             item("CONDITION_DROPPED"), item("CONDITION_DROPPED")]
    verdicts = iter([True, ec.ABSTAIN, False, ec.ABSTAIN, True])
    res = ec.score(items, lambda it: next(verdicts))
    assert res["all"]["FAITHFUL"] == {"accepted": 1, "n": 3, "rejected": 1,
                                      "abstained": 1}
    assert res["all"]["CONDITION_DROPPED"] == {"accepted": 1, "n": 2, "abstained": 1}
    assert sorted((f["class"], str(f["verdict"])) for f in res["failures"]) == [
        ("CONDITION_DROPPED", ec.ABSTAIN), ("CONDITION_DROPPED", "True"),
        ("FAITHFUL", ec.ABSTAIN), ("FAITHFUL", "False")]
    md = ec.markdown({"dev": res}, "stub")
    assert "| faithful falsely rejected | 1/3 | — |" in md
    assert "| FAITHFUL | 1/3 | 0/0 |" in md
    assert "| CONDITION_DROPPED | 1/2 | 0/0 |" in md


def test_segment_units_drops_the_preamble_and_redacts_its_names():
    rows = [(None, "This Agreement is made between Acme Widgets Pvt. Ltd, a company, and "
                   "LeapSwitch Networks Pvt Ltd."),
            ("1", "1. Acme Widgets shall pay the Fees within thirty days of invoice."),
            ("1.1", "1.1 Late payment shall attract interest."),
            ("2", "2. Notices go to Attn: the legal team, 411038.")]
    units, names = ec.segment_units(rows, "upload:x")
    assert [u.ref.split("#")[0] for u in units] == ["cl1", "cl1.1"]   # notice row dropped
    assert units[0].text.startswith("[COUNTERPARTY] shall pay")
    assert ("child", "Late payment shall attract interest.") in units[0].context
    assert "Acme Widgets" in names


def test_title_words_never_used_in_lower_case_are_redacted_as_names():
    class Cur:
        def execute(self, *_):
            pass

        def fetchall(self):
            return [("Acme services agreement", "Zylo_MSA_redline.docx")]
    got = ec._title_names(Cur(), "the services agreement is signed by the customer")
    # over-redaction ("MSA") is the safe side; lower-case filename words are not names
    assert set(got) == {"Acme", "Zylo", "MSA"}


def test_a_sentence_limited_by_a_following_proviso_is_never_labelled_faithful():
    text = ("The Customer may terminate this Agreement on thirty days written notice. "
            "Provided that no termination is permitted during the first three months.")
    unit = ec.Unit("d1", "contract", "cl1", "Clause 1", text, "CONTRACT", "CONTRACT",
                   "Under the agreement,")
    items, skips = ec.items_for([unit], "dev", 10, set())
    first = [i for i in items if i["source_sentence"].startswith("The Customer may")]
    assert first and not any(i["label"] == "FAITHFUL" for i in first)
    assert any(s["class"] == "FAITHFUL" for s in skips)

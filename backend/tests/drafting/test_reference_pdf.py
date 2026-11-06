"""A reference PDF → a DRAFT template whose party facts are typed variables (`AM-282` r2).
Synthetic segments only — an invented company, address and signatories (rule 21)."""

import json

import pytest

from legalmind.domain.enums import EvidenceSourceType
from legalmind.ingestion.parsing import Segment
from tools import import_template as T

SOURCE = {"kind": "REFERENCE_PDF", "supplier": "reference:" + "0" * 64, "file": "x.pdf",
          "sha256": "0" * 64}


def seg(content, number=None):
    return Segment(content=content, original_content=content,
                   source_type=EvidenceSourceType.NATIVE_TEXT, section_number=number)


def segments(extra_clause="Each party keeps its own costs."):
    return [
        seg("SAMPLE AGREEMENT\nThis Sample Agreement is entered into on 3rd March 2026."),
        seg("BETWEEN\nZephyr Quill Pvt. Ltd, a company incorporated under the Companies Act, "
            "2013, having its\nregistered office at 9 Placeholder Lane, Faketown - 400001 "
            "(“Disclosing Party”)."),
        seg("AND\nLeapSwitch Networks Pvt Ltd., a company having its registered office at "
            "1 Example Road, Pune - 411001, (hereinafter “Receiving Party”) through "
            "Mr. Orrin Vale, Director.\nBoth together are the “Parties”."),
        seg("WHEREAS\nThe Disclosing Party wishes to share information.\nNOW, THEREFORE, "
            "the Parties agree as follows:"),
        seg("1. Confidentiality: The Receiving Party keeps the information of Zephyr Quill "
            "Pvt Ltd. secret.", "1"),
        seg("2. COSTS\n" + extra_clause, "2"),
        seg("2.1.\nFees are ____ per month.", "2.1"),
        seg("continued on the next page.\nIN WITNESS WHEREOF the parties sign.\n"
            "| DISCLOSING PARTY | RECEIVING PARTY |\n"
            "| Zephyr Quill Pvt. Ltd. Name: Mira Stoke Title: Founder | LeapSwitch Networks "
            "Pvt Ltd Name: Orrin Vale Title: Director |"),
    ]


def load(segs, brand="LEAPSWITCH"):
    return T.from_segments(segs, source=SOURCE, template_key="REF.TEST", doc_type="NDA",
                           brand=brand, prefix="REF.")


def test_party_facts_become_variables_and_never_survive():
    template, clauses, flagged = load(segments())
    dump = json.dumps([template, list(clauses.values())]).lower()
    for fact in ("zephyr", "quill", "placeholder lane", "orrin", "vale", "mira", "stoke",
                 "3rd march"):
        assert fact not in dump
    layout = template["layout"]
    assert layout["preamble"].endswith("entered into on {effective_date}.")
    assert [p["name"] for p in layout["parties"]] == ["{counterparty_name}", "{our_name}"]
    assert [p["role"] for p in layout["parties"]] == ["Disclosing Party", "Receiving Party"]
    keys = {v["key"]: v for v in template["variables"]}
    assert keys["our_registered_office"]["locked_value"] == "1 Example Road, Pune - 411001"
    assert "locked_value" not in keys["counterparty_name"]
    first = clauses[("REF.CONFIDENTIALITY", 1)]
    assert "{counterparty_name}" in first["body"][0]["text"]
    assert any("replaced by fields" in f for f in first["source"]["flags"])
    costs = clauses[("REF.COSTS", 1)]
    assert costs["title"] == "COSTS"
    assert any("blank to fill" in f for f in costs["source"]["flags"])
    assert costs["body"][-1]["text"].endswith("per month. continued on the next page.")
    assert template["source"]["label"] == "Reference text — not approved by Legal"
    assert all(c["source"]["supplier"].startswith("reference:") for c in clauses.values())


def test_a_fact_the_rules_cannot_place_refuses_the_import():
    with pytest.raises(T.ImportRefused, match="survived"):
        load(segments(extra_clause="Zephyr-Quill pays its own costs."))


def test_a_brand_the_reference_does_not_name_is_flagged():
    template, _, flagged = load(segments(), brand="CLOUDPE")
    assert any("another of our brands" in f for f in flagged)
    assert template["brand"] == "CLOUDPE"

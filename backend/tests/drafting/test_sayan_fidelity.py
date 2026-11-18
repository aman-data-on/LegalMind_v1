"""AB-213 (AM-402/403): a contract made from the MSA reference (legal-docs/MSA.pdf) keeps
its words. The parties paragraphs, the "Party/Parties" sentence, WHEREAS, NOW THEREFORE
and IN WITNESS WHEREOF stay verbatim; agreed changes go to Annexure 2 and never into the
body. A word diff of the rendered body against the PDF differs only in filled blanks.
Needs the source material (LEGALMIND_SOURCE_MATERIAL_DIR); no legal text is written."""

from __future__ import annotations

import copy
import difflib
import html
import io
import os
import re
import subprocess
import unicodedata
import zipfile
from pathlib import Path

import pytest

from legalmind.drafting import model as model_
from legalmind.drafting import render_contract as R
from legalmind.drafting import special_conditions
from tools import import_template as T

MSA = Path(os.environ.get("LEGALMIND_SOURCE_MATERIAL_DIR", "legal-docs")) / "MSA.pdf"
pytestmark = pytest.mark.skipif(not MSA.is_file(), reason="no source material here")


def _words(text: str) -> list[str]:
    """Words only: list numbers (auto-numbered in Word) and page furniture go."""
    text = unicodedata.normalize("NFKC", html.unescape(text))
    text = re.sub(r"(?m)^\s*\d+\s*$|\f", "", text)       # page numbers
    text = re.sub(r"-\s+", "", text)
    text = text.split("Signatory Details")[0].replace("-", "")
    return [w for w in re.findall(r"[\w\u2019%()]+", text)
            if not re.fullmatch(r"\d+|[A-Za-z]|[ivx]+|\(?[a-z]\)", w)]


def _docx_text(docx: bytes) -> str:
    xml = zipfile.ZipFile(io.BytesIO(docx)).read("word/document.xml").decode()
    return re.sub(r"<[^>]+>", "", re.sub(r"<w:p[ >]", "\n<w:p ", xml))


@pytest.fixture(scope="module")
def msa():
    template, clauses, _ = T.load_pdf(MSA, template_key="MSA_T", doc_type="MSA",
                                      brand=None, prefix="MSA.")
    return template, clauses


def test_the_front_words_are_the_source_words(msa):
    layout = msa[0]["layout"]
    ours, theirs = layout["parties"]
    assert ours["incorporation"].startswith("a company incorporated under the Companies")
    assert "bearing CIN number {our_cin}" in ours["incorporation"]
    assert "registered office at {counterparty_registered_office}, bearing CIN number " \
           "{counterparty_cin}" in theirs["incorporation"]
    assert layout["connector"] == "AND" and layout["recitals_label"] == "WHEREAS"
    assert layout["parties_close"].endswith("collectively referred to as “Parties”.")
    assert layout["operative"].startswith("NOW THEREFORE")
    assert not any(r.startswith("NOW") for r in layout["recitals"])
    assert layout["execution"]["lead"] == ("IN WITNESS WHEREOF the Parties have executed "
                                           "this Agreement through their authorized "
                                           "signatories.")


def test_the_final_body_differs_from_the_msa_only_in_filled_blanks(msa):
    template, clauses = copy.deepcopy(msa)
    frame = next(c for c in __import__("json").loads(
        T.SPECIAL_REFERENCE.read_text(encoding="utf-8"))["clause_versions"]
        if (c["clause_key"], c["version"]) == ("SC.FRAME", 2))
    frame = T.check_clause(frame)
    clauses[("SC.FRAME", 2)] = frame
    cfg = {"frame": {"clause_key": "SC.FRAME", "version": 2},
           "precedence": special_conditions.IN_FRAME, "initials": False}
    template["layout"]["special_conditions"] = cfg
    template["layout"]["execution"]["last"] = True
    values = dict(template["layout"]["check_values"])
    base = model_.resolve(template, clauses, values)
    t = special_conditions.targets(base)
    agreed = {"8.3": "Agreed words for 8.3 as the parties settled them.",
              "19.4": "Agreed words for 19.4 as the parties settled them."}
    entries = [{"n": n, "op": "replace", "target": special_conditions._public(t[num]),
                "text": text} for n, (num, text) in enumerate(agreed.items(), 1)]
    model = model_.resolve(template, clauses, values,
                           special={"frame": frame, "config": cfg, "entries": entries})
    docx = R.render(model, {}, contract_ref="T", version_number=2,
                    model_hash=model_.model_hash(model))
    got = _docx_text(docx)
    body, annex = got.split("Annexure 2 — Agreed Amendments", 1)
    for text in agreed.values():
        assert text not in body and text in annex           # never in the body
    pdf = subprocess.run(["pdftotext", str(MSA), "-"], capture_output=True, text=True,
                         check=True).stdout
    # the signature page comes last, after Annexure 2 (owner: signature page last)
    a, b = _words(pdf), _words(body + annex[annex.index("IN WITNESS WHEREOF"):])
    diffs = [(" ".join(a[i1:i2]), " ".join(b[j1:j2])) for op, i1, i2, j1, j2 in
             difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
             if op != "equal"]
    filled = " ".join(values.values()) + " January 2026"
    for old, new in diffs:
        # only a blank (or the sample "Customer/Partner" name) gives way to a filled value
        assert re.fullmatch(r"[_\s]*(?:day of[_\s]*)?(?:2025)?|Customer Partner", old), \
            (old, new)
        assert all(w in filled for w in new.split()), (old, new)


def test_the_party_cin_blank_never_blocks_the_final(monkeypatch):
    """AM-402 r2 (verifier defect 1): the CIN blank the parties paragraph keeps for Legal
    is not a "blank to fill" for the final gate; any other blank still blocks."""
    from types import SimpleNamespace

    from legalmind.api.routers import negotiation as N
    party = ("LeapSwitch Networks Private Limited, a company … bearing CIN number "
             "_________________, hereinafter referred to as “LeapSwitch”")
    rows = [SimpleNamespace(content=party, section_number=None)]
    monkeypatch.setattr(N, "load_clauses", lambda db, vid: rows)
    assert N.blanks(None, SimpleNamespace(id=1)) is None
    rows.append(SimpleNamespace(content="banks at ___________ are open", section_number="1.4"))
    assert "clause 1.4" in N.blanks(None, SimpleNamespace(id=1))

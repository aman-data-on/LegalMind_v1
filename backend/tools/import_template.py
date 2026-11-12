"""Import a contract template into DRAFT rows of `clause_versions` / `template_versions`.

Two inputs:

* a template JSON under ``backend/config/templates/`` (``template.json`` beside its
  asset files) — the shape `legalmind.drafting.model` documents, with its clause
  versions inline;
* a reference DOCX (``--docx``), read from ``LEGALMIND_SOURCE_MATERIAL_DIR`` (gitignored,
  locked 54.6 — the file never enters the repository, only its rows the database):
  segmented into clauses by its heading numbering with the parser's own
  `_docx_list_numbers`, keeping tables and embedded images, and FLAGGING everything it
  cannot place (front matter, text boxes, tracked changes, an image with no alt text).

Every row is DRAFT: only a lawyer's in-app approval makes text usable (`AM-272`, plan
"Clause library & templates"). A clause without a recorded source is refused, every
content hash is recomputed (a declared hash that differs is refused), and an existing
(key, version) is skipped when its hash is equal and refused when it is not — a version
is never edited (rule 16).

Usage:
    python3 -m tools.import_template config/templates/placeholder/template.json \\
        --actor-email ops-publish@leapswitch.com [--dry-run]
    python3 -m tools.import_template --docx NDA.docx --template-key NDA.LEAPSWITCH \\
        --doc-type NDA --brand LEAPSWITCH --supplier "<lawyer>" --actor-email … --dry-run
    python3 -m tools.import_template --pdf MSA.pdf --template-key MSA.LEAPSWITCH \\
        --doc-type MSA --brand LEAPSWITCH --clause-prefix MSA_LS. --actor-email …

A reference PDF (`AM-282` r2) is read by the ingestion parser and its party-specific
facts become typed variables by a fixed rule set (`from_segments`); the supplier is
``reference:<file sha256>`` and every row is DRAFT, labelled "Reference text — not
approved by Legal". Nothing of the file enters the repository or a log: the output
names clause keys and flags, never text.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import mimetypes
import os
import re
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from legalmind import config
from legalmind.db import models as M
from legalmind.drafting import conditions
from legalmind.drafting.library import DRAFT_LABEL, TEMPLATE_FIELDS, template_hash, texts
from legalmind.drafting.model import ROLE_TEXT, clause_hash

_KEY = re.compile(r"^[A-Z][A-Z0-9_.]{0,39}$")


class ImportRefused(ValueError):
    pass


def _source_ok(source: Any) -> bool:
    return isinstance(source, dict) and bool(source.get("supplier")) and bool(source.get("kind"))


def check_clause(clause: dict[str, Any]) -> dict[str, Any]:
    """A clause version as a row would hold it, or `ImportRefused`."""
    where = f"{clause.get('clause_key')}@{clause.get('version')}"
    if not _KEY.match(str(clause.get("clause_key", ""))):
        raise ImportRefused(f"{where}: clause_key must be A-Z, 0-9, _ or . (≤ 40)")
    if not _source_ok(clause.get("source")):
        raise ImportRefused(f"{where}: no recorded source (kind and supplier) — refused")
    for k in ("title", "body"):
        if k not in clause:
            raise ImportRefused(f"{where}: missing {k}")
    out = {k: clause.get(k) for k in ("clause_key", "version", "title", "body", "stance",
                                      "source")}
    out["realises"] = clause.get("realises", [])
    digest = clause_hash(out)
    if clause.get("content_hash") not in (None, digest):
        raise ImportRefused(f"{where}: declared content_hash does not match its text")
    out["content_hash"] = digest
    return out


def check_template(template: dict[str, Any], clauses: dict[tuple[str, int], dict]) -> None:
    """Every pin known, every condition parses and names declared variables only."""
    declared = {v["key"] for v in template.get("variables", [])}
    problems = []
    for v in template.get("variables", []):
        if v.get("class", "M") not in ("M", "O", "C", "AO"):
            problems.append(f"{v['key']}: unknown class {v.get('class')}")
        if v.get("class") == "AO" and not v.get("allowed"):
            problems.append(f"{v['key']}: approved-options field with no options")
    whens = [v.get("when") for v in template.get("variables", [])]
    whens += [p.get("when") for a in [template, *template.get("annexures", [])]
              for p in a.get("clauses", [])]
    whens += [a.get("when") for a in template.get("annexures", [])]
    for when in filter(None, whens):
        try:
            unknown = conditions.names(when) - declared
        except conditions.ConditionError as exc:
            problems.append(f"condition {when}: {exc}")
            continue
        if unknown:
            problems.append(f"condition {when}: reads undeclared {sorted(unknown)}")
    for a in [template, *template.get("annexures", [])]:
        for p in a.get("clauses", []):
            if (p["clause_key"], p["version"]) not in clauses:
                problems.append(f"pin {p['clause_key']}@{p['version']}: no such clause")
    sc = (template.get("layout") or {}).get("special_conditions")
    if sc:
        frame = sc.get("frame") or {}
        if (frame.get("clause_key"), frame.get("version")) not in clauses:
            problems.append("special_conditions: the frame is no clause of this import")
        if all(p["clause_key"] != sc.get("precedence") for p in template["clauses"]):
            problems.append("special_conditions: the precedence clause is not pinned in "
                            "the body")
    if not _source_ok(template.get("source")):
        problems.append("template: no recorded source (kind and supplier)")
    if problems:
        raise ImportRefused("; ".join(problems))


def _asset(data: bytes, alt: str, media_type: str) -> dict[str, Any]:
    return {"media_type": media_type, "sha256": hashlib.sha256(data).hexdigest(),
            "data_b64": base64.b64encode(data).decode("ascii"), "alt": alt}


def load_json(path: Path) -> tuple[dict[str, Any], dict[tuple[str, int], dict]]:
    """A template JSON and its clause versions, assets embedded, hashes computed."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    clauses = {}
    for c in raw.pop("clause_versions", []):
        row = check_clause(c)
        clauses[(row["clause_key"], row["version"])] = row
    assets = {}
    for name, a in raw.get("assets", {}).items():
        file = (path.parent / a["file"]).resolve()
        if path.parent.resolve() not in file.parents:
            raise ImportRefused(f"asset {name}: outside the template's folder")
        media = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        assets[name] = _asset(file.read_bytes(), a.get("alt", ""), media)
    raw["assets"] = assets
    raw.setdefault("layout", {})["check_values"] = raw.pop("check_values", {})
    raw.pop("_note", None)
    check_template(raw, clauses)
    raw["content_hash"] = template_hash(raw, clauses)
    return raw, clauses


# ---------------------------------------------------------------- reference files
CHECK = "Check this clause"
_NUMBER = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?(?:\s+|$)")
_MARKER = re.compile(r"^(?:\(?[a-z]{1,3}\)|\(?[ivx]{1,5}\)|[•▪◦-])\s")
_MONTH = (r"(?:January|February|March|April|May|June|July|August|September|October|"
          r"November|December)")
_DATE = re.compile(rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTH},?\s+\d{{4}}\b|\b{_MONTH}\s+"
                   rf"\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}\b|\b\d{{1,2}}[/.-]\d{{1,2}}[/.-]"
                   rf"\d{{4}}\b|_{{3,}}\s*day\s+of\s+_{{3,}},?\s*\d{{4}}", re.I)
_BLANK = re.compile(r"_{3,}|\[\s*●?\s*\]")
_AMOUNT = re.compile(r"(?:Rs\.?|INR|₹)\s*\d[\d,]*", re.I)
_CIN = re.compile(r"\b[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\b")
_OURS = re.compile(r"leap\s*switch|cloud\s*pe", re.I)
_SUFFIX = re.compile(r"(?:[\s,.]+(?:pvt|private|ltd|limited|llp|inc|plc|company|co))+\.?$",
                     re.I)
_SUFFIX_OPT = r"(?:[\s,.]+(?:pvt|private|ltd|limited|llp|inc|plc|company|co)\b)*\.?"
_GENERIC = re.compile(r"^(?:the\s+)?(?:customer|partner|client|vendor|supplier|"
                      r"counterparty)(?:\s*/\s*\w+)?$", re.I)
#: words of a counterparty fact too common to prove it survived on their own
_COMMON = {"the", "and", "pvt", "private", "ltd", "limited", "llp", "india", "networks",
           "solutions", "technologies", "technology", "services", "systems", "global",
           "software", "consulting", "floor", "road", "mumbai", "pune", "delhi", "near",
           "director", "founder", "manager", "partner", "hospital", "nagar", "avenue",
           "east", "west", "north", "south", "mall", "street", "building", "tower",
           "plot", "sector", "phase", "park", "colony", "lane", "city", "district"}
_QUOTED = re.compile(r"[“\"]([^”\"]{2,40})[”\"]")
_SIGNATORY = re.compile(r"\bthrough\s+(?:Mr|Ms|Mrs|Dr)\.?\s+([A-Z][\w.]*(?:\s+[A-Z][\w.]*){0,3})")
_NAME_CELL = re.compile(r"\bName\s*[:|]\s*([A-Z][^|:\n]*?)\s*(?=Title|Designation|\||$)")


def _slug(text: str, taken: set[str], prefix: str = "") -> str:
    room = 40 - len(prefix)
    base = re.sub(r"[^A-Z0-9]+", "_", text.upper()).strip("_")[:room - 6] or "CLAUSE"
    key, n = prefix + base, 2
    while key in taken:
        key, n = f"{prefix}{base}_{n}", n + 1
    taken.add(key)
    return key


class _Placer:
    """Numbered text → clauses: a top-level number starts a clause, deeper numbers nest
    as subs (a skipped level nests under the one above), anything else is a block of the
    deepest open clause. What cannot be placed is flagged, never dropped silently."""

    def __init__(self, source: dict[str, Any], prefix: str, flagged: list[str]) -> None:
        self.source, self.prefix, self.flagged = source, prefix, flagged
        self.clauses: list[dict[str, Any]] = []
        self.stack: list[list[dict]] = []
        self.taken: set[str] = set()
        self.last: dict[str, Any] | None = None

    def flag(self, why: str) -> None:
        if self.clauses:
            self.clauses[-1]["source"]["flags"].append(why)
        self.flagged.append(f"{self.clauses[-1]['clause_key'] if self.clauses else 'front'}"
                            f": {why}")

    def clause(self, number: str, title: str) -> list[dict]:
        body: list[dict] = []
        self.clauses.append({"clause_key": _slug(title, self.taken, self.prefix),
                             "version": 1, "title": title, "body": body, "realises": [],
                             "stance": None,
                             "source": {**self.source, "clause": number, "flags": []}})
        self.stack = [body]
        self.last = None
        return body

    def sub(self, number: str, text: str) -> dict[str, Any] | None:
        depth = len(number.split("."))
        if not self.clauses or self.clauses[-1]["source"]["clause"] != number.split(".")[0]:
            self.clause(number.split(".")[0], f"Clause {number.split('.')[0]}")
            self.flag(f"clause {number.split('.')[0]} has no heading of its own")
        if depth > 5:
            self.flag(f"clause {number} nests deeper than five levels")
            return self.block({"kind": "p", "text": text})
        while len(self.stack) < depth - 1:
            self.stack.append(self.stack[-1])
        sub: dict[str, Any] = {"kind": "sub", "text": text, "body": []}
        self.stack[depth - 2].append(sub)
        self.stack = [*self.stack[:depth - 1], sub["body"]]
        self.last = sub
        return sub

    def block(self, block: dict[str, Any]) -> dict[str, Any] | None:
        if not self.clauses:
            self.flagged.append("front: text before the first numbered clause is not placed")
            return None
        self.stack[-1].append(block)
        if "text" in block:
            self.last = block
        return block


def load_docx(path: Path, *, template_key: str, doc_type: str, brand: str | None,
              supplier: str, approval_ref: str | None, prefix: str = ""
              ) -> tuple[dict[str, Any], dict[tuple[str, int], dict], list[str]]:
    """A reference DOCX → (template, clauses, flagged). Clauses start at each top-level
    number Word displays; deeper numbers nest as subs; tables and embedded images are
    kept in the clause they stand in; everything else that cannot be placed is flagged,
    never dropped silently."""
    import docx
    from docx.oxml.ns import qn

    from legalmind.ingestion.parsing import _docx_list_numbers, _docx_text, normalize_text

    data = path.read_bytes()
    document = docx.Document(io.BytesIO(data))
    body = document.element.body
    paragraphs = body.xpath(".//w:p[not(ancestor::w:txbxContent)]")
    numbers = _docx_list_numbers(document, paragraphs)
    typed = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(\S.*)$")
    source = {"kind": "REFERENCE_DOCX", "supplier": supplier, "approval_ref": approval_ref,
              "file": path.name, "sha256": hashlib.sha256(data).hexdigest()}
    flagged: list[str] = []
    if body.xpath(".//w:ins | .//w:del | .//w:moveFrom | .//w:moveTo"):
        flagged.append("the file carries tracked changes — accept or reject them first")
    if body.xpath(".//w:txbxContent"):
        flagged.append("text boxes are not placed")
    assets: dict[str, Any] = {}
    place = _Placer(source, prefix, flagged)

    def blocks(parent: Any):
        """Paragraphs and tables in reading order, content controls looked through."""
        for el in parent:
            if el.tag == qn("w:sdt"):
                yield from blocks(el.find(qn("w:sdtContent")))
            elif el.tag in (qn("w:p"), qn("w:tbl")):
                yield el

    for el in blocks(body):
        if el.tag == qn("w:tbl"):
            rows = [[normalize_text(" ".join(_docx_text(p) for p in tc.iter(qn("w:p"))))
                     for tc in tr.findall(qn("w:tc"))] for tr in el.findall(qn("w:tr"))]
            if rows and len({len(r) for r in rows}) == 1:
                place.block({"kind": "table", "header": rows[0], "rows": rows[1:]})
            else:
                place.flag("a table with merged or uneven rows is not placed")
            continue
        text = normalize_text(_docx_text(el)).replace("{", "(").replace("}", ")")
        for blip in el.iter(qn("a:blip")):
            rid = blip.get(qn("r:embed"))
            part = document.part.related_parts.get(rid) if rid else None
            descr = next((d.get("descr") for d in el.iter(qn("wp:docPr"))), "") or ""
            if part is None:
                place.flag("a linked (not embedded) image is not placed")
                continue
            if not descr:
                place.flag("an image has no alt text")
            name = f"image_{len(assets) + 1}"
            assets[name] = _asset(part.blob, descr, part.content_type)
            place.block({"kind": "image", "asset": name, "alt": descr, "width_cm": 12})
        if not text:
            continue
        number = numbers.get(el)
        m = None if number else typed.match(text)
        if m:
            number, text = m.group(1), m.group(2)
        if number and "." not in number:
            place.clause(number, text)
        elif number:
            place.sub(number, text)
        else:
            place.block({"kind": "p", "text": text})
    layout = {"title": path.stem, "short_title": path.stem}
    return _finish(place, layout, [], source, assets, template_key=template_key,
                   doc_type=doc_type, brand=brand)


def _finish(place: _Placer, layout: dict[str, Any], variables: list[dict[str, Any]],
            source: dict[str, Any], assets: dict[str, Any], *, template_key: str,
            doc_type: str, brand: str | None
            ) -> tuple[dict[str, Any], dict[tuple[str, int], dict], list[str]]:
    checked = {(c["clause_key"], 1): check_clause(c) for c in place.clauses}
    template: dict[str, Any] = {
        "template_key": template_key, "version": 1, "doc_type": doc_type, "brand": brand,
        "layout": layout, "variables": variables,
        "clauses": [{"clause_key": k, "version": 1} for k, _ in checked],
        "annexures": [], "assets": assets,
        "source": {**source, "label": DRAFT_LABEL, "flags": list(place.flagged)}}
    check_template(template, checked)
    template["content_hash"] = template_hash(template, checked)
    return template, checked, place.flagged


# ------------------------------------------------- reference PDF (`AM-282` r2)
_CONNECTOR = re.compile(r"(?:BETWEEN|AND|BY AND BETWEEN:?|WHEREAS|[A-Z]\.)", re.I)


def _paragraphs(text: str, *, front: bool = False) -> list[str]:
    """Wrapped PDF lines → paragraphs: a list marker or a table row starts a new one;
    a bare page number is page furniture and goes. Before clause 1 (``front``) a
    connector line ("BETWEEN", "A.") stands alone and a line ending a sentence ends its
    paragraph — the party blocks and recitals are told apart by that."""
    out: list[str] = []
    closed = False
    for raw in text.split("\n"):
        line = raw.strip().replace("\u200b", "")
        if not line or line.isdigit():
            closed = closed or not line            # a blank line ends a paragraph
            continue
        alone = front and bool(_CONNECTOR.fullmatch(line))
        if (not out or _MARKER.match(line) or line.startswith("|")
                or out[-1].startswith("|") or alone or closed):
            out.append(line)
        elif out[-1].endswith("-"):
            out[-1] += line
        else:
            out[-1] += " " + line
        closed = front and (alone or line.endswith((".", ":", ";", ")")) or len(out) == 1)
    return [p.replace("{", "(").replace("}", ")") for p in out]


def _table(rows: list[str]) -> dict[str, Any] | None:
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    return ({"kind": "table", "header": cells[0], "rows": cells[1:]}
            if len({len(r) for r in cells}) == 1 else None)


def _party(paragraph: str) -> dict[str, Any]:
    terms = [t for t in _QUOTED.findall(paragraph)
             if t not in ("Agreement", "Parties", "Party")]
    name = re.split(r",\s|\s\(", paragraph, maxsplit=1)[0].strip()
    office = re.search(r"registered office at\s+(.+?)(?=,?\s*\(|,\s*bearing|,\s*hereinafter"
                       r"|$)", paragraph)
    cin = _CIN.search(paragraph)
    return {"role": terms[0] if terms else None, "name": name,
            "ours": bool(_OURS.search(name)), "office": office.group(1).strip(" ,")
            if office else None, "cin": cin.group(0) if cin else None,
            "signatories": _SIGNATORY.findall(paragraph)}


def _front(paragraphs: list[str], flagged: list[str]
           ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Title, preamble, parties and recitals out of the text before clause 1."""
    title = paragraphs[0] if paragraphs else "Agreement"
    preamble: list[str] = []
    parties: list[dict[str, Any]] = []
    recitals: list[str] = []
    part = "preamble"
    for p in paragraphs[1:]:
        bare = p.strip().rstrip(":").upper()
        if bare in ("BETWEEN", "AND", "BY AND BETWEEN") or re.fullmatch(r"[A-Z]\.", p):
            continue
        if bare == "WHEREAS":
            part = "recitals"
            continue
        if "registered office" in p.lower():
            parties.append(_party(p))
            part = "after parties"
        elif part == "recitals":
            if p.upper().startswith("NOW"):
                flagged.append("front: the words of agreement are placed as the last "
                               f"recital — {CHECK.lower()}")
            recitals.append(p)
        elif part == "preamble":
            preamble.append(p)
        else:
            flagged.append("front: a sentence after the parties is not placed")
    if len(parties) != 2 or sum(p["ours"] for p in parties) != 1:
        flagged.append(f"front: {len(parties)} party blocks found, not one of ours and one "
                       f"counterparty — {CHECK.lower()} (parties)")
    return {"title": title, "preamble": " ".join(preamble), "recitals": recitals}, parties


def _execution(text: str) -> list[str]:
    return [n.strip() for n in _NAME_CELL.findall(text) if n.strip()]


def _variables(parties: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ours = next((p for p in parties if p["ours"]), {})

    def var(key: str, group: str, cls: str = "M", kind: str = "text",
            locked: str | None = None) -> dict[str, Any]:
        words, help_ = ROLE_TEXT[key]            # the form's words, from the role
        v = {"key": key, "label": words, **({"help": help_} if help_ else {}),
             "type": kind, "group": group, "class": cls}
        return {**v, "locked_value": locked} if locked else v

    return [var("effective_date", "Deal", kind="date"),
            var("our_name", "Our company", locked=(ours.get("name") or "").rstrip(".")),
            var("our_registered_office", "Our company", locked=ours.get("office")),
            var("our_cin", "Our company", "O", locked=ours.get("cin")),
            var("our_signatory_name", "Our company"),
            var("our_signatory_designation", "Our company"),
            var("our_signatory_email", "Our company"),
            var("counterparty_name", "Client"),
            var("counterparty_registered_office", "Client"),
            var("counterparty_cin", "Client", "O"),
            var("counterparty_signatory_name", "Client"),
            var("counterparty_signatory_designation", "Client"),
            var("counterparty_signatory_email", "Client")]


CHECK_VALUES = {"effective_date": "2026-01-01", "our_signatory_name": "Check Signatory One",
                "our_signatory_designation": "Director",
                "our_signatory_email": "check.signatory.one@example.test",
                "counterparty_name": "Check Client Private Limited",
                "counterparty_registered_office": "Check Address, Pune 411001",
                "counterparty_signatory_name": "Check Signatory Two",
                "counterparty_signatory_designation": "Director",
                "counterparty_signatory_email": "check.signatory.two@example.test"}


def _scrubber(parties: list[dict[str, Any]], signers: list[str]
              ) -> tuple[list[tuple[re.Pattern[str], str]], list[str]]:
    """(patterns → variable slot, the facts that must not survive). The counterparty's
    name is matched on its core (company suffixes off, any whitespace between words), so
    "X Pvt. Ltd", "X Pvt Ltd." and a line-wrapped "X\\nPvt" all go."""
    rules: list[tuple[re.Pattern[str], str]] = []
    facts: list[str] = []

    def words(s: str) -> str:
        return r"\s+".join(map(re.escape, s.split()))

    for p in parties:
        side = "our" if p["ours"] else "counterparty"
        if not p["ours"]:
            core = _SUFFIX.sub("", p["name"]).strip(" ,.")
            if core and not _GENERIC.match(core):
                rules.append((re.compile(words(core) + _SUFFIX_OPT, re.I), "{counterparty_name}"))
                facts.append(core)
            if p["office"] and not _BLANK.search(p["office"]):
                rules.append((re.compile(words(p["office"]), re.I),
                              "{counterparty_registered_office}"))
                facts.append(p["office"])
            if p["cin"]:
                rules.append((re.compile(re.escape(p["cin"])), "{counterparty_cin}"))
                facts.append(p["cin"])
        for s in p["signatories"]:
            rules.append((re.compile(words(s)), f"{{{side}_signatory_name}}"))
            facts.append(s)
    for s in signers:
        if s not in facts:
            rules.append((re.compile(words(s)), "{counterparty_signatory_name}"
                          if not _OURS.search(s) else "{our_signatory_name}"))
            facts.append(s)
    return rules, facts


def _scrub(text: str, rules: list[tuple[re.Pattern[str], str]]) -> str:
    for pattern, slot in rules:
        text = pattern.sub(slot, text)
    return text


def _scrub_tree(node: Any, rules: list[tuple[re.Pattern[str], str]]) -> None:
    """Every string of a clause tree (its source excepted) through `_scrub`."""
    items = enumerate(node) if isinstance(node, list) else \
        ((k, v) for k, v in node.items() if k != "source")
    for k, x in list(items):
        if isinstance(x, str):
            node[k] = _scrub(x, rules)
        elif isinstance(x, list | dict):
            _scrub_tree(x, rules)


def from_segments(segments: list[Any], *, source: dict[str, Any], template_key: str,
                  doc_type: str, brand: str | None, prefix: str
                  ) -> tuple[dict[str, Any], dict[tuple[str, int], dict], list[str]]:
    """The parser's segments of a reference PDF → a DRAFT template whose party-specific
    facts are typed variables. Deterministic: the party blocks (text before clause 1 that
    names a registered office), the signature block (from "IN WITNESS WHEREOF"), dates and
    blanks. A counterparty fact that survives anywhere refuses the import."""
    flagged: list[str] = []
    place = _Placer(source, prefix, flagged)
    front: list[str] = []
    execution: list[str] = []
    for seg in segments:
        content = seg.content
        if execution or "IN WITNESS WHEREOF" in content.upper():
            at = content.upper().find("IN WITNESS WHEREOF")
            if not execution and at > 0:
                content, tail = content[:at], content[at:]
                execution.append(tail)
            else:
                execution.append(content)
                continue
        number = seg.section_number
        if number is None:
            # a heading the parser left inside the text before it ("1.\nDEFINITIONS")
            m = re.search(r"\n(\d+)\.?\s*\n([^\n]{1,80})\s*$", "\n" + content)
            if m:
                head = _paragraphs(content[:m.start()])
                if place.clauses:
                    for p in head:
                        place.block({"kind": "p", "text": p})
                else:
                    front.extend(_paragraphs(content[:m.start()], front=True))
                place.clause(m.group(1), m.group(2).strip())
                continue
        text = _NUMBER.sub("", content, count=1) if number else content
        heading, _, rest = text.strip().partition("\n")
        if number and "." not in number and heading.isupper() and rest:
            text = heading + "\n\n" + rest      # an upper-case first line is the heading
        paras = _paragraphs(text)
        if number is None and not place.clauses:
            front.extend(_paragraphs(content, front=True))
            continue
        if number and "." not in number:
            first = paras.pop(0) if paras else f"Clause {number}"
            titled = re.match(r"^([^:.]{2,60}):\s+(.+)$", first)
            if titled:
                place.clause(number, titled.group(1))
                paras.insert(0, titled.group(2))
            elif first.isupper() or len(first) <= 60:
                place.clause(number, first)
            else:
                place.clause(number, f"Clause {number}")
                place.flag(f"clause {number} has no heading of its own")
                paras.insert(0, first)
        elif number:
            place.sub(number, paras.pop(0) if paras else "")
        elif paras and paras[0][:1].islower() and place.last is not None:
            place.last["text"] += " " + paras.pop(0)
        elif paras and not _MARKER.match(paras[0]):
            place.flag(f"an unnumbered paragraph after a page break is placed here — {CHECK}")
        rows: list[str] = []
        for p in [*paras, ""]:
            if p.startswith("|"):
                rows.append(p)
                continue
            if rows:
                table = _table(rows)
                if table:
                    place.block(table)
                else:
                    place.flag("a table with uneven rows is not placed")
                rows = []
            if p:
                place.block({"kind": "p", "text": p})
    layout, parties = _front(front, flagged)
    signers = _execution("\n".join(execution))
    if not execution:
        flagged.append(f"front: no signature block found — {CHECK.lower()} (execution)")
    rules, facts = _scrubber(parties, signers)
    _scrub_tree(place.clauses, rules)
    layout["preamble"] = _scrub(_DATE.sub("{effective_date}", layout["preamble"], count=1),
                                rules)
    layout["recitals"] = [_scrub(r, rules) for r in layout["recitals"]]
    for c in place.clauses:
        flat = " ".join(texts([c["title"], c["body"]]))
        for why, pattern in (("states a date", _DATE), ("has a blank to fill", _BLANK),
                             ("states an amount", _AMOUNT)):
            if pattern.search(flat):
                c["source"]["flags"].append(f"{why} — {CHECK}")
                flagged.append(f"{c['clause_key']}: {why}")
        if "{counterparty_" in flat:
            c["source"]["flags"].append(f"party details were replaced by fields — {CHECK}")
    for where, text in (("preamble", layout["preamble"]),
                        *(("recitals", r) for r in layout["recitals"])):
        if _BLANK.search(text):
            flagged.append(f"front: a blank to fill in the {where} — {CHECK.lower()}")
    roles = {("our" if p["ours"] else "counterparty"): p["role"] for p in parties}
    sides = [("our" if p["ours"] else "counterparty") for p in parties] or \
        ["our", "counterparty"]
    layout.update({
        "short_title": layout["title"].title()[:40],
        "parties": [{"role": roles.get(s) or ("LeapSwitch" if s == "our" else "Client"),
                     "name": f"{{{s}_name}}", "office": f"{{{s}_registered_office}}",
                     "cin": f"{{{s}_cin}}"} for s in sides],
        "execution": {"rows": [{"party": f"{{{s}_name}}", "signatory":
                                f"{{{s}_signatory_name}}", "designation":
                                f"{{{s}_signatory_designation}}", "email":
                                f"{{{s}_signatory_email}}"} for s in sides],
                      "seal": False, "witness": False},
        "check_values": dict(CHECK_VALUES)})
    ours = next((p for p in parties if p["ours"]), None)
    if brand and ours and brand.replace("_", "").lower() not in \
            re.sub(r"\s+", "", ours["name"]).lower():
        flagged.append(f"front: the reference names another of our brands as our party; "
                       f"this {brand} template keeps those entity details until the lawyer "
                       f"confirms them — {CHECK.lower()} (parties)")
    variables = _variables(parties)
    for v in variables:
        if v["key"].startswith("our_") and v["class"] == "M" and "signatory" not in v["key"] \
                and not v.get("locked_value"):
            v["class"] = "O"
            flagged.append(f"front: {v['key']} is not stated in the reference — "
                           f"{CHECK.lower()}")
    template, checked, flagged = _finish(place, layout, variables, source, {},
                                         template_key=template_key, doc_type=doc_type,
                                         brand=brand)
    dump = json.dumps([template["layout"], list(checked.values())],
                      ensure_ascii=False)
    flat = " ".join(dump.split()).lower()
    tokens = {w for f in facts for w in re.findall(r"[A-Za-z]{3,}", f)
              if w.lower() not in _COMMON}
    survived = [f for f in facts if " ".join(f.split()).lower() in flat]
    survived += [w for w in tokens if re.search(rf"\b{re.escape(w.lower())}\b", flat)]
    if survived:
        raise ImportRefused(f"{len(survived)} party-specific fact(s) survived the "
                            "variable rules — refused, nothing written")
    return template, checked, flagged


def load_pdf(path: Path, *, template_key: str, doc_type: str, brand: str | None,
             prefix: str) -> tuple[dict[str, Any], dict[tuple[str, int], dict], list[str]]:
    """A reference PDF read by the ingestion parser (no OCR) → `from_segments`."""
    from legalmind.ingestion.parsing import parse_pdf

    data = path.read_bytes()
    parsed = parse_pdf(data, ocr=False)
    digest = hashlib.sha256(data).hexdigest()
    source = {"kind": "REFERENCE_PDF", "supplier": f"reference:{digest}",
              "approval_ref": None, "file": path.name, "sha256": digest}
    return from_segments(parsed.segments, source=source, template_key=template_key,
                         doc_type=doc_type, brand=brand, prefix=prefix)


# ---------------------------------------------------------------- database
def import_rows(db: Session, template: dict[str, Any], clauses: dict[tuple[str, int], dict],
                *, actor_id: Any) -> list[str]:
    """DRAFT rows for every clause and the template. Idempotent by content hash."""
    lines = []
    for (key, version), c in clauses.items():
        existing = db.execute(select(M.ClauseVersion).where(
            M.ClauseVersion.clause_key == key, M.ClauseVersion.version == version)
        ).scalar_one_or_none()
        if existing is not None:
            if existing.content_hash != c["content_hash"]:
                raise ImportRefused(f"{key}@{version} exists with different text — "
                                    "a new version is needed, never an edit")
            lines.append(f"unchanged clause {key}@{version} ({existing.status})")
            continue
        db.add(M.ClauseVersion(**{k: c[k] for k in (
            "clause_key", "version", "title", "body", "realises", "stance", "source",
            "content_hash")}, status="DRAFT", created_by=actor_id))
        lines.append(f"DRAFT clause {key}@{version}")
    existing_t = db.execute(select(M.TemplateVersion).where(
        M.TemplateVersion.template_key == template["template_key"],
        M.TemplateVersion.version == template["version"])).scalar_one_or_none()
    if existing_t is not None:
        if existing_t.content_hash != template["content_hash"]:
            raise ImportRefused(f"template {template['template_key']}@{template['version']}"
                                " exists with different content")
        lines.append(f"unchanged template {template['template_key']}@{template['version']}")
    else:
        db.add(M.TemplateVersion(
            template_key=template["template_key"], version=template["version"],
            status="DRAFT", content_hash=template["content_hash"], created_by=actor_id,
            **{k: template.get(k) for k in TEMPLATE_FIELDS}))
        lines.append(f"DRAFT template {template['template_key']}@{template['version']}")
    db.flush()
    return lines


SPECIAL_REFERENCE = (Path(__file__).resolve().parents[1] / "config" / "templates"
                     / "special_conditions" / "reference.json")


def precedence_version(db: Session, tv: M.TemplateVersion, clause_key: str, *,
                       actor_id: Any) -> M.ClauseVersion:
    """A new DRAFT version of the body clause ``clause_key`` whose own "Order of
    Precedence" sub-clause keeps its words and gains the reference precedence sentence
    (design §5: the precedence is that clause's, never a second clause saying it)."""
    import copy

    from sqlalchemy import func
    pin = next((p for p in tv.clauses if p["clause_key"] == clause_key), None)
    if pin is None:
        raise ImportRefused(f"{clause_key} is not a body clause of this template")
    row = db.execute(select(M.ClauseVersion).where(
        M.ClauseVersion.clause_key == clause_key,
        M.ClauseVersion.version == pin["version"])).scalar_one()
    raw = json.loads(SPECIAL_REFERENCE.read_text(encoding="utf-8"))
    sentence = raw["clause_versions"][1]["body"][0]["text"]
    body = copy.deepcopy(row.body)
    subs = [b for b in body if b.get("kind") == "sub"
            and "precedence" in (b.get("title") or "").lower()]
    if len(subs) != 1:
        raise ImportRefused(f"{clause_key} has no one sub-clause titled with "
                            "“Order of Precedence” to hold the precedence sentence")
    if sentence not in subs[0]["text"]:
        subs[0]["text"] = f"{subs[0]['text'].rstrip()} {sentence}"
    clause = {"title": row.title, "body": body, "realises": row.realises,
              "stance": row.stance}
    latest = db.execute(select(func.max(M.ClauseVersion.version)).where(
        M.ClauseVersion.clause_key == clause_key)).scalar_one()
    made = M.ClauseVersion(clause_key=clause_key, version=latest + 1, status="DRAFT",
                           **clause, content_hash=clause_hash(clause),
                           source={"kind": "model", "label": "For management approval",
                                   "supplier": "LegalMind engineering (AM-307 "
                                               "reference text)", "approval_ref": None,
                                   "based_on": {"version": row.version,
                                                "content_hash": row.content_hash}},
                           created_by=actor_id)
    db.add(made)
    db.flush()
    tv.clauses = [{**p, "version": made.version} if p["clause_key"] == clause_key else p
                  for p in tv.clauses]
    return made


def attach_special_conditions(db: Session, tv: M.TemplateVersion, *, actor_id: Any,
                              position: str = "after_execution",
                              initials: bool = True,
                              precedence_into: str | None = None) -> list[str]:
    """`AM-307` B1: the DRAFT reference frame (`SPECIAL_REFERENCE`, "For management
    approval") as a DRAFT row and ``layout.special_conditions`` set, on a DRAFT template
    version only (an approved one is frozen). The precedence sentence goes into the
    body clause ``precedence_into`` as a new DRAFT version of it (its "Order of
    Precedence" sub-clause); without one — a template that has no such clause — the
    reference precedence clause is pinned last in the body. Nothing here is approved:
    the lawyer approves both on the Template approval page (rules 7/21)."""
    if tv.status != "DRAFT":
        raise ImportRefused(f"{tv.template_key}@{tv.version} is {tv.status}; attach the "
                            "Special Conditions to a draft version")
    raw = json.loads(SPECIAL_REFERENCE.read_text(encoding="utf-8"))
    clauses = {(c["clause_key"], c["version"]): check_clause(c)
               for c in raw["clause_versions"]}
    frame, precedence = (k for k in clauses)
    lines = []
    for (key, version), c in clauses.items():
        if precedence_into and key == precedence[0]:
            continue
        existing = db.execute(select(M.ClauseVersion).where(
            M.ClauseVersion.clause_key == key, M.ClauseVersion.version == version)
        ).scalar_one_or_none()
        if existing is None:
            db.add(M.ClauseVersion(**{k: c[k] for k in (
                "clause_key", "version", "title", "body", "realises", "stance", "source",
                "content_hash")}, status="DRAFT", created_by=actor_id))
            lines.append(f"DRAFT clause {key}@{version}")
        elif existing.content_hash != c["content_hash"]:
            raise ImportRefused(f"{key}@{version} exists with different text")
    if precedence_into:
        made = precedence_version(db, tv, precedence_into, actor_id=actor_id)
        lines.append(f"DRAFT clause {made.clause_key}@{made.version} (precedence)")
        key = precedence_into
    else:
        key = precedence[0]
        if all(p["clause_key"] != key for p in tv.clauses):
            tv.clauses = [*tv.clauses, {"clause_key": key, "version": precedence[1]}]
    tv.layout = {**(tv.layout or {}), "special_conditions": {
        "frame": {"clause_key": frame[0], "version": frame[1]},
        "precedence": key, "position": position, "pages": "continue",
        "initials": initials}}
    db.flush()
    from legalmind.drafting.library import _rehash
    _rehash(db, tv)
    db.flush()
    return [*lines, f"special conditions attached to {tv.template_key}@{tv.version}"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", nargs="?", help="template JSON")
    parser.add_argument("--docx", help="reference DOCX, relative to the source directory")
    parser.add_argument("--pdf", help="reference PDF, relative to the source directory")
    parser.add_argument("--clause-prefix", default="",
                        help="prefix for the clause keys, e.g. NDA_LS. (≤ 8 characters)")
    parser.add_argument("--template-key")
    parser.add_argument("--doc-type")
    parser.add_argument("--brand")
    parser.add_argument("--supplier", help="who supplied the reference text (required)")
    parser.add_argument("--approval-ref")
    parser.add_argument("--actor-email", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--special-conditions", metavar="TEMPLATE_KEY",
                        help="attach the DRAFT Special Conditions frame and precedence "
                             "clause to the latest DRAFT version of this template")
    parser.add_argument("--precedence-into", metavar="CLAUSE_KEY",
                        help="with --special-conditions: the body clause whose “Order of "
                             "Precedence” sub-clause takes the precedence sentence")
    args = parser.parse_args()
    try:
        flagged: list[str] = []
        if args.special_conditions:
            with Session(create_engine(config.database_url())) as db:
                actor = db.execute(select(M.User).where(
                    M.User.email == args.actor_email)).scalar_one_or_none()
                tv = db.execute(select(M.TemplateVersion).where(
                    M.TemplateVersion.template_key == args.special_conditions,
                    M.TemplateVersion.status == "DRAFT")
                    .order_by(M.TemplateVersion.version.desc())).scalars().first()
                if actor is None or tv is None:
                    raise ImportRefused("no such user, or no DRAFT version of that key")
                print("\n".join(attach_special_conditions(
                    db, tv, actor_id=actor.id, precedence_into=args.precedence_into)))
                db.rollback() if args.dry_run else db.commit()
            return 0
        if args.docx or args.pdf:
            root = Path(os.environ.get("LEGALMIND_SOURCE_MATERIAL_DIR", "legal-docs")).resolve()
            file = (root / (args.docx or args.pdf)).resolve()
            if root not in file.parents:
                raise ImportRefused("the reference must be a file inside the source directory")
            if not (args.template_key and args.doc_type):
                raise ImportRefused("a reference needs --template-key and --doc-type")
            if args.pdf:
                template, clauses, flagged = load_pdf(
                    file, template_key=args.template_key, doc_type=args.doc_type,
                    brand=args.brand, prefix=args.clause_prefix)
            else:
                if not args.supplier:
                    raise ImportRefused("--docx needs --supplier")
                template, clauses, flagged = load_docx(
                    file, template_key=args.template_key, doc_type=args.doc_type,
                    brand=args.brand, supplier=args.supplier,
                    approval_ref=args.approval_ref, prefix=args.clause_prefix)
        elif args.path:
            template, clauses = load_json(Path(args.path))
        else:
            raise ImportRefused("name a template JSON or --docx")
        engine = create_engine(config.database_url())
        with Session(engine) as db:
            actor = db.execute(select(M.User).where(M.User.email == args.actor_email)
                               ).scalar_one_or_none()
            if actor is None:
                raise ImportRefused(f"no user {args.actor_email}")
            lines = import_rows(db, template, clauses, actor_id=actor.id)
            if args.dry_run:
                db.rollback()
            else:
                db.commit()
    except ImportRefused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    print("\n".join(lines + [f"FLAGGED: {f}" for f in flagged]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

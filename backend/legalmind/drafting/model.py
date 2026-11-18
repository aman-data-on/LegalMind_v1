"""A template version + a person's answers → the canonical contract model.

The model is plain JSON: every clause kept by its condition, numbered L1–L5 as the
document will display it, every ``{xref:key}`` resolved to that number, every ``{var}``
to a validated value. ``model_hash`` (sha256 of its canonical JSON) is the determinism
key — the same template version and the same answers give the same hash, whatever the
renderer's bytes (`AM-251` r1: no model in this path, nothing composed).

Text is FIXED. The only inputs are declared variables; an unknown answer, a missing
mandatory one, a value outside its allowed set or range, a slot naming nothing, an xref
to a clause the conditions left out, or a defined term used and never defined are
refused — every problem named with its field, never filled in (rule 15).

Template (the shape `tools/import_template.py` loads and `template_versions` stores)::

    {"template_key", "version", "doc_type", "brand",
     "layout": {"title", "short_title", "preamble",
                "parties": [{role, name, office, cin, incorporation?}],
                "recitals": [text],
                "connector"?, "parties_close"?, "recitals_label"?, "operative"?,
                "execution": {"rows": [{party, signatory, designation, authority?, email?,
                                 date?}], "seal", "witness", "lead"?, "last"?}},

The ``?`` front-matter texts are optional and enter the model only when the template has
them (so a template without them keeps its model hash): ``connector`` between the
parties ("AND"), ``parties_close`` after them, ``recitals_label`` over the recitals
("WHEREAS"), ``operative`` after them ("NOW THEREFORE, …"), a party's ``incorporation``
after its bold name in the same paragraph (it states the party's role itself, so the
``(“Role”)`` is not added), execution ``lead`` above the signature table ("IN WITNESS
WHEREOF …"), execution ``last`` (S2): the signature page after every schedule and
annexure, on a page of its own — the file's last page.
     "variables": [{key, type, group, class: M|O|C|AO, when, allowed, range,
                    locked_value, help}],
     "clauses": [{clause_key, version, when?}],
     "annexures": [{key, title, when?, clauses: [pins]}],
     "assets": {"logo:<BRAND>": {media_type, sha256, data_b64, alt}, "<name>": {...}}}

Clause body blocks: ``p`` · ``heading`` · ``sub`` (numbered, nests to L5) · ``list`` ·
``definition`` · ``table`` · ``image``. A ``sub`` may carry a run-in ``title`` ("Term:",
"Billing and Invoicing") printed before its ``text`` — underlined, or bold when
``title_style`` is ``"bold"``, as the source file set it; ``title + text`` is the
clause's wording. Slots: ``{var}``, ``{xref:key}``, ``{term:Name}``.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from legalmind.drafting import conditions, special_conditions

MAX_LEVEL = 5
#: the optional front-matter texts (see the layout above)
FRONT = ("connector", "parties_close", "recitals_label", "operative")
CLASSES = {"M", "O", "C", "AO"}
TYPES = {"text", "date", "int", "bool", "choice", "email", "rows"}
#: a ``rows`` answer's ceiling (S4: one fee line per service taken)
MAX_ROWS = 50
#: an unmapped service's 5.3 cell (S4, rule 21): Legal writes it, never LegalMind
LEGAL_TO_SUPPLY = "[Legal to supply]"
#: AM-402 r2: an optional party fact nobody gave (a CIN) prints as the source's blank
OPEN_BLANK = "_________________"
#: AM-397: what `legal_to_supply` names for an annexure whose words Legal owes
ANNEXURE_TEXT = "the Annexure 1 wording"
#: an email address as a signing tool needs one (S2): local part, @, a dotted domain
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
#: ``{name}`` · ``{xref:CLAUSE.KEY}`` · ``{term:Defined Term}``
SLOT = re.compile(r"\{(?:(xref|term):)?([A-Za-z_][\w .\-]*)\}")
_TEXT_MAX = 500
_TERM = r"[“\"]([^”\"]+)[”\"]"
#: how a drafter defines a term, wherever it stands — the file's own (preflight) reading
#: and the model's agree: a paragraph opening on “X”; (“X”), (the “X”) and a short
#: lead-in such as (together, the “X”) or (hereinafter “X”); “X” means / shall mean /
#: shall have the meaning / refers to, and each term of a chain (“X” or “Y” shall mean);
#: referred to as (a) “X” (or “Y”)
_REFERRED = r"referred\s+to\s+as\s+(?:an?\s+|the\s+)?"
DEFINES = (
    re.compile(r"^" + _TERM),
    re.compile(r"\((?:[^()“\"]{0,40}?\s)?(?:the\s+)?" + _TERM + r"\)"),
    re.compile(_TERM + r"(?=(?:\s*(?:,|or|and)\s*[“\"][^”\"]+[”\"])*\s*(?:shall\s+"
               # "shall be construed accordingly": derived forms of the term just
               # defined (MSA 1.1.2's “Controls” or “Controlled by”, 2026-11-04)
               r"(?:mean|have\s+the\s+meaning|include|refer|be\s+construed\s+accordingly)|"
               r"means\b|refers?\s+to\b|has\s+the\s+meaning))", re.I),
    # the party block's own: (hereinafter) referred to as (a) “X” (or “Y”)
    re.compile(_REFERRED + _TERM, re.I),
    re.compile(_REFERRED + r"[“\"][^”\"]+[”\"]\s+or\s+" + _TERM, re.I))


def defined_terms(text: str) -> set[str]:
    return {m.group(1) for pattern in DEFINES for m in pattern.finditer(text)}


class ModelError(ValueError):
    """Every problem found, each ``{"field": …, "problem": …}`` — never only the first."""

    def __init__(self, problems: list[dict[str, str]]) -> None:
        super().__init__("; ".join(f"{p['field']}: {p['problem']}" for p in problems))
        self.problems = problems


# ---------------------------------------------------------------- what a person reads
#: a variable's ROLE (its ``role``, else its key — the importer's keys are roles) → the
#: words the form asks it in and its help. Form labels, never contract wording.
ROLE_TEXT: dict[str, tuple[str, str | None]] = {
    "effective_date": ("Effective date", "The date this agreement takes effect."),
    "counterparty_name": ("Client's legal name",
                          "As registered, for example Acme Private Limited."),
    "counterparty_registered_office": ("Client's registered office",
                                       "As on their certificate of incorporation."),
    "counterparty_cin": ("Client's CIN or LLPIN", "21 characters, for example "
                         "U72900MH2010PTC123456, or an LLPIN such as AAB-1234."),
    "counterparty_pan": ("Client's PAN", "10 characters, for example ABCDE1234F."),
    "counterparty_gstin": ("Client's GSTIN",
                           "15 characters, for example 27ABCDE1234F1Z5."),
    "counterparty_entity_type": ("Client's entity type",
                                 "For example, private limited company or LLP."),
    "counterparty_notice_address": ("Client's address for notices", None),
    "counterparty_notice_email": ("Client's email for notices", None),
    "counterparty_signatory_name": ("Who signs for the client",
                                    "The person authorised to sign for them."),
    "counterparty_signatory_designation": ("Their designation", "For example, Director."),
    "counterparty_authority": ("Their authority to sign", "For example, a board "
                               "resolution or letter of authority, with its date."),
    "our_name": ("Our company", None),
    "our_registered_office": ("Our registered office", None),
    "our_cin": ("Our CIN", None),
    "our_signatory_name": ("Who signs for us", "The person authorised to sign for us."),
    "our_signatory_designation": ("Their designation", "For example, Director."),
    "our_authority": ("Their authority to sign", None),
    "our_signatory_email": ("Their email", "Where the signing tool sends the contract."),
    "counterparty_signatory_email": ("Their email",
                                     "Where the signing tool sends the contract."),
}


def role(var: Mapping[str, Any]) -> str:
    return var.get("role") or var["key"]


def label(var: Mapping[str, Any]) -> str:
    """The author's label, else the role's, else the key made readable (refused at
    publish — `key_like`)."""
    return (var.get("label") or ROLE_TEXT.get(role(var), (None,))[0]
            or var["key"].replace("_", " ").capitalize())


def help_text(var: Mapping[str, Any]) -> str | None:
    return var.get("help") or ROLE_TEXT.get(role(var), (None, None))[1]


def key_like(var: Mapping[str, Any]) -> bool:
    """A label no author wrote: none given and no role's words, or one with an
    underscore in it ("party_two_cin", "Party two cin")."""
    given = var.get("label") or ROLE_TEXT.get(role(var), (None,))[0]
    return not given or "_" in given


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def content_hash(obj: Any) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def clause_hash(clause: Mapping[str, Any]) -> str:
    """What a lawyer approves: the title, the body and what it realises."""
    return content_hash({k: clause.get(k)
                         for k in ("title", "body", "realises", "stance")})


# ---------------------------------------------------------------- answers
def _coerce(var: Mapping[str, Any], raw: Any) -> Any:
    kind = var.get("type", "text")
    if kind == "choice" and var.get("multi"):          # S4: services taken
        if not isinstance(raw, list) or not raw:
            raise ValueError("must be one or more of the approved options")
        if len(set(map(str, raw))) != len(raw):
            raise ValueError("names an option twice")
        if any(x not in var.get("allowed", []) for x in raw):
            raise ValueError("is not one of the approved options")
        return list(raw)
    if kind == "rows":                                  # S4: the fee table
        cols = {c["key"]: c for c in var.get("columns", [])}
        if not isinstance(raw, list) or not raw or len(raw) > MAX_ROWS:
            raise ValueError(f"must have 1 to {MAX_ROWS} rows")
        out = []
        for i, row in enumerate(raw, 1):
            if not isinstance(row, dict) or set(row) != set(cols):
                raise ValueError(f"row {i} must give exactly: {', '.join(cols)}")
            cells = {}
            for k, c in cols.items():
                try:
                    cells[k] = _coerce(c, row[k])
                except ValueError as exc:
                    raise ValueError(f"row {i}, {c.get('label', k)}, {exc}") from None
                if "allowed" in c and cells[k] not in c["allowed"]:
                    raise ValueError(f"row {i}, {c.get('label', k)}, is not one of the "
                                     "approved options")
            out.append(cells)
        return out
    if kind == "bool":
        if not isinstance(raw, bool):
            raise ValueError("must be yes or no")
        return raw
    if kind == "int":
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise ValueError("must be a whole number")
        lo, hi = (var.get("range") or [None, None])
        if (lo is not None and raw < lo) or (hi is not None and raw > hi):
            raise ValueError(f"must be between {lo} and {hi}")
        return raw
    if kind == "date":
        try:
            return dt.date.fromisoformat(str(raw)).isoformat()
        except ValueError:
            raise ValueError("must be a date (YYYY-MM-DD)") from None
    text = " ".join(str(raw).split())        # control characters and runs of space go
    if not text:
        raise ValueError("is empty")
    if len(text) > _TEXT_MAX:
        raise ValueError(f"is longer than {_TEXT_MAX} characters")
    if "{" in text or "}" in text:
        raise ValueError("may not contain { or }")
    if kind == "email" and not EMAIL.fullmatch(text):
        raise ValueError("must be an email address, for example name@company.com")
    return text


def validate(variables: list[Mapping[str, Any]],
             answers: Mapping[str, Any]) -> dict[str, Any]:
    """The answers checked against the declared variables → the values the model uses."""
    declared = {v["key"]: v for v in variables}
    problems = [{"field": k, "problem": "is not a field of this template"}
                for k in sorted(set(answers) - set(declared))]
    values: dict[str, Any] = {}
    # unconditional fields first, so a condition reads checked values
    for var in sorted(variables, key=lambda v: v.get("class") == "C"):
        key, cls = var["key"], var.get("class", "M")
        if cls == "C" and not conditions.evaluate(var.get("when"), values):
            continue                                    # not asked: no value
        raw = answers.get(key)
        if "locked_value" in var:
            if raw is not None and raw != var["locked_value"]:
                problems.append({"field": key, "problem": "is fixed by our standard and "
                                 "cannot be changed here"})
            raw = var["locked_value"]
        if (raw is None or raw == "") and var.get("default"):
            raw = var["default"]        # AM-394: the value Legal set for an empty blank
        if raw is None or raw == "":
            if cls != "O":
                problems.append({"field": key, "problem": "is required"})
            continue
        try:
            value = _coerce(var, raw)
        except ValueError as exc:
            problems.append({"field": key, "problem": str(exc)})
            continue
        if "allowed" in var and not isinstance(value, list) \
                and value not in var["allowed"]:
            problems.append({"field": key,
                             "problem": "is not one of the approved options"})
            continue
        values[key] = value
    if problems:
        raise ModelError(problems)
    return values


def _display(var: Mapping[str, Any] | None, value: Any) -> str:
    if var and var.get("type") == "date":
        d = dt.date.fromisoformat(value)
        return f"{d.day} {d:%B %Y}"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, list):
        return "; ".join(_display(None, x) for x in value)
    return str(value)


# ---------------------------------------------------------------- resolution
class _Resolver:
    def __init__(self, template: Mapping[str, Any], values: dict[str, Any],
                 mark: bool = False, blank: bool = False) -> None:
        self.vars = {v["key"]: v for v in template.get("variables", [])}
        self.values = values
        self.mark = mark
        self.blank = blank
        self.problems: list[dict[str, str]] = []
        self.numbers: dict[str, str] = {}
        self.defined: set[str] = set()
        self.terms_used: list[tuple[str, str]] = []
        self.xrefs: list[tuple[str, str]] = []
        #: (clause_key, the sub's own words, its number): what `{delivery}` points at
        self.subs: list[tuple[str, str, str]] = []
        self.delivery = template.get("layout", {}).get("delivery", {})

    def runs(self, text: str, where: str, *, optional: bool = False) -> list[dict] | None:
        """Text → runs: ``{"t"}`` plain, ``{"ref", "num"}`` a cross-reference (number
        filled in by `_fill_refs`). None when ``optional`` and a variable has no value."""
        out: list[dict] = []
        pos = 0
        for m in SLOT.finditer(text):
            if m.start() > pos:
                out.append({"t": text[pos:m.start()]})
            kind, name = m.group(1), m.group(2)
            if kind == "xref":
                self.xrefs.append((name, where))
                out.append({"ref": name, "num": None})
            elif kind == "term":
                self.terms_used.append((name, where))
                out.append({"t": name})
            elif name not in self.vars:
                self.problems.append({"field": where, "problem":
                                      f"uses {{{name}}}, which is not a field"})
            elif name not in self.values and self.blank:
                out.append(placeholder(self.vars[name]))
            elif name not in self.values and optional:
                return None
            elif name not in self.values and self.vars[name].get("class") == "O" \
                    and where == "parties":
                out.append({"t": OPEN_BLANK})     # AM-402 r2: for Legal, never made up
            elif name not in self.values:
                if optional:
                    return None
                self.problems.append({"field": name,
                                      "problem": f"has no value but {where} uses it"})
            else:
                out.append({"t": _display(self.vars[name], self.values[name]),
                            **({"var": name} if self.mark else {})})
            pos = m.end()
        if pos < len(text):
            out.append({"t": text[pos:]})
        return _merge(out)

    def blocks(self, body: list[Mapping[str, Any]], where: str, prefix: list[int],
               level: int) -> list[dict]:
        out: list[dict] = []
        sub = 0
        for block in body:
            kind = block.get("kind")
            if kind == "sub":
                if level + 1 > MAX_LEVEL:
                    self.problems.append({"field": where, "problem":
                                          f"nests deeper than {MAX_LEVEL} levels"})
                    continue
                sub += 1
                number = ".".join(map(str, [*prefix, sub]))
                self.defined |= defined_terms(block.get("text", ""))
                if block.get("key"):
                    self._number(block["key"], number, where)
                self.subs.append((where.split("@")[0],
                                  block.get("title", "") + block.get("text", ""), number))
                out.append({"kind": "sub", "key": block.get("key"), "level": level + 1,
                            "number": number,
                            **{k: block[k] for k in ("title", "title_style")
                               if k in block},
                            "runs": self.runs(block.get("text", ""), where),
                            "body": self.blocks(block.get("body", []), where,
                                                [*prefix, sub], level + 1)})
            elif kind == "p" and block["text"] == LEGAL_TO_SUPPLY:
                # AM-397: an annexure whose words Legal has not supplied yet (L3) —
                # a stand-in that blocks Final (`legal_to_supply`), never our text
                out.append({"kind": kind, "runs": [{"t": LEGAL_TO_SUPPLY, "ph": True,
                                                    "legal": ANNEXURE_TEXT}]})
            elif kind in ("p", "heading"):
                self.defined |= defined_terms(block["text"])
                out.append({"kind": kind, "runs": self.runs(block["text"], where)})
            elif kind == "definition":
                self.defined |= {block["term"], *defined_terms(block["text"])}
                out.append({"kind": kind, "term": block["term"],
                            "runs": self.runs(block["text"], where)})
            elif kind == "list":
                out.append({"kind": kind, "items": [self.runs(t, where)
                                                    for t in block["items"]]})
            elif kind == "table" and block.get("rows_from"):
                out.append({"kind": kind, "widths": block.get("widths"),
                            "rows": [[self.runs(c, where) for c in block["header"]],
                                     *self.filled(block, where)]})
            elif kind == "table":
                rows = [block["header"], *block.get("rows", [])]
                if len({len(r) for r in rows}) != 1:
                    self.problems.append({"field": where, "problem":
                                          "a table row has the wrong cell count"})
                    continue
                out.append({"kind": kind, "widths": block.get("widths"),
                            "rows": [[self.runs(c, where) for c in r] for r in rows]})
            elif kind == "image":
                out.append({"kind": kind, "asset": block["asset"],
                            "alt": block.get("alt", ""),
                            "width_cm": block.get("width_cm", 8)})
            else:
                self.problems.append({"field": where,
                                      "problem": f"has a block of unknown kind {kind!r}"})
        return out

    def filled(self, block: Mapping[str, Any], where: str) -> list[list[list[dict]]]:
        """S4: one row per item of the field ``rows_from`` names; a cell is ``{item}``,
        ``{item.<column>}``, ``{delivery}`` (the item's clause 5.3 number) or slot text.
        The blank template: one row of the headers in brackets."""
        var = self.vars.get(block["rows_from"])
        if var is None:
            self.problems.append({"field": where, "problem": f"fills a table from "
                                  f"{block['rows_from']}, which is not a field"})
            return []
        if self.blank and var["key"] not in self.values:
            return [[[{"t": f"[{h}]", "ph": True}]
                     for h in block["header"]]]
        rows = []
        for item in self.values.get(var["key"], []):
            row = []
            for cell in block["cells"]:
                if cell == "{item}":
                    row.append([{"t": _display(None, item)}])
                elif cell.startswith("{item.") and cell.endswith("}"):
                    row.append([{"t": _display(None, item.get(cell[6:-1], ""))}])
                elif cell == "{delivery}":
                    row.append([self.delivered(item if isinstance(item, str)
                                               else item.get("service", ""), where)])
                else:
                    row.append(self.runs(cell, where) or [])
            rows.append(row)
        return rows

    def delivered(self, service: str, where: str) -> dict:
        """The number of the body sub whose own words start as ``layout.delivery`` maps
        the service (5.3.1 for "VPS Services:"), or the Legal-to-supply run (rule 21)."""
        if not service:
            self.problems.append({"field": where, "problem": "names no service for a "
                                  "clause 5.3 cell"})
            return {"t": ""}
        starts = self.delivery.get("lines", {}).get(service)
        if starts is None:
            return {"t": LEGAL_TO_SUPPLY, "ph": True, "legal": service}
        clause = self.delivery.get("clause")
        found = [n for k, text, n in self.subs if k == clause and text.startswith(starts)]
        if len(found) != 1:
            self.problems.append({"field": where, "problem": f"maps {service} to "
                                  f"“{starts}”, which {len(found)} sub-clauses of "
                                  f"{clause} start with"})
            return {"t": ""}
        return {"t": found[0]}

    def _number(self, key: str, number: str, where: str) -> None:
        if key in self.numbers:
            self.problems.append({"field": where, "problem": f"repeats the key {key}"})
        self.numbers[key] = number


#: a blank template's bracketed note on a conditional part — what `negotiation` drops
#: from the comparison when the paper comes back
NOTE_OPEN = "[Optional: "


#: a placeholder where the form's own label leans on the question beside it ("Their
#: designation" under "Who signs for us")
PLACEHOLDER_TEXT = {
    "counterparty_signatory_name": "Client signatory's name",
    "counterparty_signatory_designation": "Client signatory's designation",
    "counterparty_authority": "Client signatory's authority to sign",
    "our_signatory_name": "Our signatory's name",
    "our_signatory_designation": "Our signatory's designation",
    "our_authority": "Our signatory's authority to sign",
    "our_signatory_email": "Our signatory's email",
    "counterparty_signatory_email": "Client signatory's email",
}


def placeholder(var: Mapping[str, Any]) -> dict:
    """A field's visible stand-in on the blank template: its label in brackets."""
    return {"t": f"[{PLACEHOLDER_TEXT.get(role(var)) or label(var)}]", "ph": True}


def _condition(expr: Any, vars: Mapping[str, Mapping[str, Any]]) -> str | None:
    """A condition in the form's own words, or None when it is not a plain comparison
    of declared fields (the note then says only that it may not apply)."""
    if not isinstance(expr, dict) or len(expr) != 1:
        return None
    (op, args), = expr.items()
    if op in ("and", "or") and isinstance(args, list):
        parts = [_condition(a, vars) for a in args]
        return None if None in parts else f" {op} ".join(map(str, parts))
    if op in ("==", "!=") and isinstance(args, list) and len(args) == 2 \
            and isinstance(args[0], dict) and "var" in args[0] \
            and args[0]["var"] in vars and not isinstance(args[1], dict | list):
        var = vars[args[0]["var"]]
        said = _display(var, args[1]) if var.get("type") != "date" else str(args[1])
        return f"“{label(var)}” is {'not ' if op == '!=' else ''}{said}"
    return None


def note(expr: Any, vars: Mapping[str, Mapping[str, Any]]) -> str:
    words = _condition(expr, vars)
    return (f"{NOTE_OPEN}include this only if {words}; otherwise delete it.]" if words
            else f"{NOTE_OPEN}include this only where it applies; otherwise delete it.]")


def _merge(runs: list[dict]) -> list[dict]:
    out: list[dict] = []
    for r in runs:
        if set(r) == {"t"} and out and set(out[-1]) == {"t"}:
            out[-1] = {"t": out[-1]["t"] + r["t"]}
        else:
            out.append(r)
    return out


def _fill_refs(node: Any, numbers: Mapping[str, str]) -> None:
    if isinstance(node, list):
        for x in node:
            _fill_refs(x, numbers)
    elif isinstance(node, dict):
        if "ref" in node:
            node["num"] = numbers.get(node["ref"])
        for x in node.values():
            if isinstance(x, list | dict):
                _fill_refs(x, numbers)


def _pins(r: _Resolver, pins: list[Mapping[str, Any]],
          clauses: Mapping[tuple[str, int], Mapping[str, Any]],
          section: str) -> list[dict]:
    out: list[dict] = []
    for pin in pins:
        optional = pin.get("when", True) is not True
        if not r.blank and not conditions.evaluate(pin.get("when", True), r.values):
            continue
        clause = clauses.get((pin["clause_key"], pin["version"]))
        where = f"{pin['clause_key']}@{pin['version']}"
        if clause is None:
            r.problems.append({"field": where, "problem": "is not in the clause library"})
            continue
        n = len(out) + 1
        r._number(pin["clause_key"], str(n), where)
        out.append({"clause_key": pin["clause_key"], "version": pin["version"],
                    "content_hash": clause.get("content_hash") or clause_hash(clause),
                    "section": section, "number": str(n),
                    "title": clause.get("title", ""),
                    "body": r.blocks(clause.get("body", []), where, [n], 1),
                    **({"note": note(pin["when"], r.vars)} if r.blank and optional
                       else {})})
    return out


#: a blank in approved text: a run of three or more underscores ("banks at ______")
UNDERSCORES = re.compile(r"_{3,}")
#: a blank and a lone space before the punctuation after it (dropped once filled)
_BLANK_IN_TEXT = re.compile(r"_{3,}(?: (?=[.,;:]))?")


def blank_runs(node: Any) -> list[dict[str, str]]:
    """Each underscore blank in ``node``'s strings, in order, with the words before and
    after it — the ``n`` (1-based) a ``blank`` field names."""
    out: list[dict[str, str]] = []

    def walk(x: Any) -> None:
        if isinstance(x, str):
            out.extend({"before": " ".join(x[max(0, m.start() - 40):m.start()].split()),
                        "after": " ".join(x[m.end():m.end() + 30].split())}
                       for m in UNDERSCORES.finditer(x))
        elif isinstance(x, list | dict):
            for y in x.values() if isinstance(x, dict) else x:
                walk(y)
    walk(node)
    return out


def _fill_blanks(template: Mapping[str, Any],
                 clauses: Mapping[tuple[str, int], Mapping[str, Any]],
                 values: Mapping[str, Any]) -> tuple[Mapping[str, Any], Mapping]:
    """`AM-392`: a field Legal made of a blank (``"blank": {"in", "n"}`` — a clause key,
    or ``preamble``/``recitals``) takes the n-th underscore run's place there, ONLY when
    the deal answered it. Unanswered, the underscores stay and Final is blocked
    (`negotiation.blanks`). The approved words (and their hash) never change: only this
    render's copy is filled."""
    want: dict[str, dict[int, str]] = {}
    for v in template.get("variables", []):
        if (b := v.get("blank")) and values.get(v["key"]) not in (None, ""):
            want.setdefault(b["in"], {})[int(b["n"])] = v["key"]
    if not want:
        return template, clauses

    def fill(node: Any, slots: dict[int, str], seen: list[int]) -> Any:
        if isinstance(node, str):
            def one(m: re.Match) -> str:
                seen[0] += 1
                key = slots.get(seen[0])
                if not key:
                    return m.group(0)
                # AM-394: the source glues a blank to the next word ("___are") or spaces
                # it from a full stop ("___ ."); the filled copy reads as a sentence
                glued = m.end() < len(node) and node[m.end()].isalnum()
                return "{" + key + "}" + (" " if glued else "")
            return _BLANK_IN_TEXT.sub(one, node)
        if isinstance(node, list):
            return [fill(x, slots, seen) for x in node]
        if isinstance(node, dict):
            return {k: fill(x, slots, seen) for k, x in node.items()}
        return node
    clauses = {k: ({**c, "body": fill(c.get("body"), want[c["clause_key"]], [0])}
                   if c.get("clause_key") in want else c) for k, c in clauses.items()}
    layout = dict(template.get("layout") or {})
    for where in ("preamble", "recitals"):
        if where in want and where in layout:
            layout[where] = fill(layout[where], want[where], [0])
    return {**template, "layout": layout}, clauses


def resolve(template: Mapping[str, Any],
            clauses: Mapping[tuple[str, int], Mapping[str, Any]],
            answers: Mapping[str, Any], *, mark: bool = False,
            blank: bool = False,
            special: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """The canonical model, or `ModelError` naming every problem. ``mark`` (the
    preview's) tags each filled value's run with its field — ``{"t", "var"}`` — so a
    value can be linked to its question; the canonical model (and its hash) never has
    it. ``blank`` (the blank template, owner 2026-11-04): no answers — every field not
    fixed by our standard is a visible placeholder run ``{"t": "[Label]", "ph": True}``,
    and every conditional clause and schedule is kept with a bracketed ``note``.
    ``special`` (`AM-307`): ``{"frame": clause, "config", "entries"}`` — the Special
    Conditions section, under ``model["special_conditions"]``; without it the key is
    absent and the model (and its hash) is exactly as before."""
    values = ({v["key"]: v["locked_value"] for v in template.get("variables", [])
               if "locked_value" in v} if blank
              else validate(template.get("variables", []), answers))
    template, clauses = _fill_blanks(template, clauses, values)
    r = _Resolver(template, values, mark, blank)
    layout = template.get("layout", {})
    body = _pins(r, template.get("clauses", []), clauses, "main")
    schedules = []
    for annex in template.get("annexures", []):
        if blank or conditions.evaluate(annex.get("when", True), values):
            schedules.append({"key": annex["key"], "title": annex["title"],
                              "clauses": _pins(r, annex.get("clauses", []), clauses,
                                               annex["key"]),
                              **({"note": note(annex["when"], r.vars)}
                                 if blank and annex.get("when", True) is not True
                                 else {})})
    parties = []
    for p in layout.get("parties", []):
        parties.append({"role": p["role"], "name": r.runs(p["name"], "parties"),
                        "office": r.runs(p.get("office", ""), "parties", optional=True),
                        "cin": r.runs(p.get("cin", ""), "parties", optional=True)})
        r.defined.add(p["role"])
        if p.get("incorporation"):
            parties[-1]["incorporation"] = r.runs(p["incorporation"], "parties")
            r.defined |= defined_terms(p["incorporation"])
    front = {k: r.runs(layout[k], k) for k in FRONT if layout.get(k)}
    r.defined |= {t for k in FRONT for t in defined_terms(layout.get(k) or "")}
    execution = layout.get("execution") or {}
    rows = [{k: r.runs(v, "execution", optional=k in ("authority", "email", "date"))
             for k, v in row.items()}
            for row in execution.get("rows", [])]
    assets = template.get("assets", {})
    logo = assets.get(f"logo:{template.get('brand')}")
    for name, where in r.xrefs:
        if name not in r.numbers:
            r.problems.append({"field": where, "problem": f"refers to {name}, which this "
                               "contract does not contain"})
    for term, where in r.terms_used:
        if term not in r.defined:
            r.problems.append({"field": where, "problem":
                               f"uses the term “{term}”, which is never defined"})
    images = sorted({b["asset"] for b in _walk(body + schedules)
                     if b.get("kind") == "image"})
    for name in images:
        if name not in assets:
            r.problems.append({"field": name, "problem": "image is not among the assets"})
    if r.problems:
        raise ModelError(r.problems)
    model = {
        "template": {k: template.get(k)
                     for k in ("template_key", "version", "content_hash")},
        "doc_type": template.get("doc_type"), "brand": template.get("brand"),
        "title": layout.get("title", ""), "short_title": layout.get("short_title", ""),
        "preamble": r.runs(layout.get("preamble", ""), "preamble"),
        "parties": parties,
        "recitals": [r.runs(t, "recitals") for t in layout.get("recitals", [])],
        "body": body, "schedules": schedules,
        **front,
        "execution": {"rows": rows, "seal": bool(execution.get("seal")),
                      "witness": bool(execution.get("witness")),
                      **({"lead": r.runs(execution["lead"], "execution")}
                         if execution.get("lead") else {}),
                      **({"last": True} if execution.get("last") else {})},
        "logo": ({"sha256": logo["sha256"], "alt": logo.get("alt", "")}
                 if logo else None),
        "images": {n: assets[n]["sha256"] for n in images},
        "values": values,
    }
    _fill_refs(model, r.numbers)
    model["numbers"] = dict(sorted(r.numbers.items()))
    if special is not None and special.get("entries"):
        sc, anchors = special_conditions.section(r, special["frame"], special["config"],
                                                 special["entries"], layout, model)
        numbers = {**r.numbers, **anchors}
        named = special_conditions.targets(model)
        for e in ([] if special["config"].get("external") else special["entries"]):
            t = e.get("target")
            if t and (named.get(t["number"]) or {}).get("key") != t["key"]:
                r.problems.append({"field": "special_conditions", "problem":
                                   f"entry {e['n']} names clause {t['number']}, which "
                                   "this contract does not number so"})
        if r.problems:
            raise ModelError(r.problems)
        _fill_refs(sc, numbers)
        model["special_conditions"] = sc
    return model


def _walk(node: Any):
    if isinstance(node, list):
        for x in node:
            yield from _walk(x)
    elif isinstance(node, dict):
        yield node
        for x in node.values():
            if isinstance(x, list | dict):
                yield from _walk(x)


def legal_to_supply(model: Mapping[str, Any]) -> list[str]:
    """S4 (spec g5): the services whose clause 5.3 cell waits for Legal, in order."""
    return list(dict.fromkeys(n["legal"] for n in _walk(model) if "legal" in n))


def model_hash(model: Mapping[str, Any]) -> str:
    return content_hash(model)


def text_of(runs: list[dict] | None) -> str:
    """Runs as the reader sees them (an xref as its number)."""
    return "".join(r["t"] if "t" in r else str(r["num"]) for r in runs or [])

"""The amendment instrument — changes only (`AM-310`; Q-9 decided as research 13 (c)).

"Prepare amendment" composes a short instrument from the approved AMENDMENT template:
its recitals name the governing contract (name and signing date), its Schedule of
Changes lists THIS amendment's own changes in the frame's fixed verbs ("Clause 8.5 …
is deleted and replaced with:"), then the template's own no-other-change, precedence
and counterparts clauses and its signature blocks. Every legal word is the template's;
code fills only variables and the change list (rules 7/21, `AM-251` r1). A template
that lacks a slot the instrument needs is refused with the slot named — never filled.

The whole contract restated (form (b)) stays the final-contract package itself, open
only to a holder of `legal.approve_customization` (the router's gate). The conformed
copy is the Terms in force view, derived on demand and never signed.

The layout an AMENDMENT template opts in with::

    "special_conditions": {"frame": {clause_key, version}}   # the change sentences
    "amendment": {"no_other_change", "precedence", "counterparts"}   # body clause keys

and variables whose ``role`` is ``governing_agreement``, ``governing_signed_on`` and
``effective_date`` (``amendment_number`` optional). Any other variable takes the value
the governing contract's own draft gave the same key (the parties' names, signatories).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.drafting import model as model_
from legalmind.drafting import publish, special_conditions

#: variable roles the code fills, and how a missing one is named
FILLED = {"governing_agreement": "a variable for the governing contract's name",
          "governing_signed_on": "a variable for its signing date",
          "effective_date": "a variable for the effective date"}
CLAUSES = {"no_other_change": "the no-other-change clause",
           "precedence": "the precedence clause",
           "counterparts": "the counterparts clause"}
#: Q-9 restatement prompts — PRODUCT HEURISTICS for the lawyer to confirm (research 13
#: §2.2: no source states a number). The UI suggests, never selects, and says so.
# ponytail: constants in code; move to configuration when Legal sets their own
PRIOR_AMENDMENTS = 3
ROOT_HEADING = re.compile(r"\b(parties|term|duration|governing law|jurisdiction)\b", re.I)


def missing(db: DBSession, tv: M.TemplateVersion) -> list[str]:
    """Every slot this AMENDMENT template lacks for a changes-only instrument, in plain
    words — [] when it can carry one."""
    out = [f"the change wording ({m['detail']})" for m in
           special_conditions.frame_missing(special_conditions.frame_row(db, tv))]
    roles = {model_.role(v) for v in tv.variables or []}
    out += [said for r, said in FILLED.items() if r not in roles]
    cfg = (tv.layout or {}).get("amendment") or {}
    rows = publish.pinned_clauses(db, tv)
    for slot, said in CLAUSES.items():
        row = next((c for (k, _), c in rows.items() if k == cfg.get(slot)), None)
        if row is None or not any(p["clause_key"] == row.clause_key for p in tv.clauses):
            out.append(said)
        elif row.status != "APPROVED":
            out.append(f"{said} approved by Legal")
    if not ((tv.layout or {}).get("execution") or {}).get("rows"):
        out.append("the signature blocks")
    return out


def values(tv: M.TemplateVersion, filled: Mapping[str, Any],
           governing: Mapping[str, Any]) -> dict[str, Any]:
    """The instrument's answers: a code-filled role's value, else the governing
    contract's own value for the same key, else nothing (validate names it required)."""
    out: dict[str, Any] = {}
    for v in tv.variables or []:
        if "locked_value" in v:
            continue
        r = model_.role(v)
        value = filled.get(r) if r in filled or r == "amendment_number" \
            else governing.get(v["key"])
        if value not in (None, ""):
            out[v["key"]] = value
    return out


def build(db: DBSession, tv: M.TemplateVersion, answers: Mapping[str, Any],
          entries: list[dict]) -> dict[str, Any]:
    """The instrument's model: the template, its answers, and the changes as the
    frame's numbered sentences before the signature blocks. The changes name the
    governing contract's clause numbers as plain text (they are not this document's)."""
    frame = special_conditions.frame_row(db, tv)
    assert frame is not None                  # `missing` said so first
    clauses = {k: publish.clause_dict(c)
               for k, c in publish.pinned_clauses(db, tv).items()}
    return model_.resolve(publish.template_dict(tv), clauses, answers, special={
        "frame": publish.clause_dict(frame), "entries": entries,
        "config": {"position": "before_execution", "external": True}})


def restatement_reasons(prior_signed: int, entries: list[dict]) -> list[str]:
    """Why Legal might prefer the whole contract restated — said, never acted on."""
    out = []
    if prior_signed >= PRIOR_AMENDMENTS:
        out.append(f"This contract already has {prior_signed} signed amendments.")
    for e in entries:
        t = e.get("target") or {}
        if ROOT_HEADING.search(t.get("heading") or ""):
            out.append(f"Clause {t['number']} ({t['heading']}) goes to the root of the "
                       "contract.")
    return out


def apply(units: list[dict], entries: list[dict]) -> list[dict]:
    """The text in force after a changes-only amendment: each change applied to the
    clauses it names — replaced, deleted, or inserted after. The entries are the
    prepared record, which the signed copy was checked against before signing.
    ``ValueError`` when a change names a clause the text does not hold (fail closed)."""
    out = [dict(u) for u in units]
    for e in entries:
        number = e["target"]["number"]
        at = next((i for i, u in enumerate(out) if u["number"] == number), None)
        if at is None:
            raise ValueError(f"a change names clause {number}, which the text in force "
                             "does not hold")
        lines = [x for x in (e.get("text") or "").split("\n") if x.strip()]
        if e["op"] == "delete":
            del out[at]
        elif e["op"] == "insert_after":
            out.insert(at + 1, _unit(e["new_number"], None, lines))
        else:
            unit = out[at]
            keep = unit["texts"][:1] if "." not in number and unit.get("heading") else []
            out[at] = _unit(number, unit.get("heading"), keep + lines)
    return out


def _unit(number: str | None, heading: str | None, texts: list[str]) -> dict[str, Any]:
    text = "\n".join(texts)
    return {"number": number, "heading": heading, "texts": texts, "text": text,
            "original": text, "changes": [], "evidence_ids": [], "page": None,
            "part": False}

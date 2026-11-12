"""The negotiation playbook — what the deal owner may agree without Legal (`AM-305`,
owner requirement 2026-11-04 from the manager's direction).

Our paper opens with our best position; the ratified Company Standard is how far we go.
For each point the engine measured on our paper, derived and never authored (rules 7/21):

* **opening** — what our own paper says, as the engine read it (the Evaluation's
  ``actual_value`` on our version's Review, or on the published template's rendered file);
* **limit** — the ratified standard's own position (``preferred``/``unit``/``basis``,
  ``mutual``), quoted from the configuration snapshot the Review was run on;
* **kind** — ``RANGE``: the standard declares a ``favourable_direction`` the engine
  accepts without Legal (the approved favourable rule, no Counsel check, LeapSwitch the
  provider), or is a cap a lower mutual figure of which is ours (`AM-299` r3 /
  `AM-301`): anything from the limit toward our side is the deal owner's to agree.
  ``EXACT``: a numeric or categorical standard with no such direction — only the
  standard's own value. ``LEGAL_ONLY``: anything else — Legal decides any change.

The playbook decides nothing (the five axes): what a client's change does is still
`negotiation.effect_for_us`, from the engine's Findings; `within` restates the same band
so a test can hold the two together. ``fallbacks`` are intermediate steps a Legal approver
recorded on a template clause version (``source.fallbacks``) — none is seeded.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.analysis import negotiation
from legalmind.db import models as M
from legalmind.evaluation.rule_config import (
    FAVOURABLE_COUNSEL_CHECK,
    FAVOURABLE_DIRECTION,
    FAVOURABLE_OUTCOME,
)

RANGE, EXACT, LEGAL_ONLY = "RANGE", "EXACT", "LEGAL_ONLY"
#: a fee basis in a salesperson's words; any other basis (a day count's) goes unsaid
_BASIS = {"FEES_PAID": "total fees",
          "FEES_PAID_FOR_AFFECTED_SERVICES": "fees for the affected services"}
_UNIT = {"PERCENT_PER_MONTH": "percent a month", "PERCENT_PER_ANNUM": "percent a year"}


def _amount(value: Any, unit: str | None, basis: str | None) -> str:
    words = _UNIT.get(unit or "", (unit or "").lower().replace("_", " "))
    if value == 1 and words.endswith("s") and "percent" not in words:
        words = words[:-1]
    return f"{value:g} {words}" + (f" of {_BASIS[basis]}" if basis in _BASIS else "")


def _side(actual: dict | None) -> dict | None:
    """The one figure a single Evaluation read, or None (not read, several, unlimited)."""
    if not actual or not isinstance(actual.get("cap_value"), (int, float)) \
            or not actual.get("cap_unit"):
        return None
    return {"value": actual["cap_value"], "unit": actual["cap_unit"],
            "basis": actual.get("cap_basis"), "party": actual.get("cap_party")}


def _standard_side(standard: dict) -> dict | None:
    preferred, unit = standard.get("preferred"), standard.get("unit")
    if not isinstance(preferred, (int, float)) or not unit:
        return None
    return {"value": preferred, "unit": unit, "basis": standard.get("basis"),
            "party": "both" if standard.get("mutual") else None}


def entry(code: str, standard: dict, legal_rule: dict | None, opening: dict | None,
          *, provider: bool, fallbacks: list[dict] | None = None,
          whose: str = "Our paper") -> dict[str, Any]:
    """One point's playbook line, from the standard and our paper's figure alone.
    ``whose`` names where the opening figure comes from (Batch 1 c): our paper, or —
    the paper not provably ours — our standard."""
    preferred, unit = standard.get("preferred"), standard.get("unit")
    allowed = standard.get("allowed_values") or []
    out: dict[str, Any] = {"requirement_code": code, "opening": opening,
                           "limit": None, "direction": None, "fallbacks": []}
    if isinstance(preferred, (int, float)) and unit:
        mutual = bool(standard.get("mutual"))
        out["limit"] = {"value": preferred, "unit": unit, "basis": standard.get("basis"),
                        "mutual": mutual}
        direction = standard.get(FAVOURABLE_DIRECTION)
        favoured = (direction in ("LOWER", "HIGHER")
                    and not standard.get(FAVOURABLE_COUNSEL_CHECK)
                    and (legal_rule or {}).get(FAVOURABLE_OUTCOME) == "ACCEPTABLE")
        if code in negotiation.LOWER_CAP_IS_OURS:
            direction, favoured = "LOWER", True
        out["kind"] = RANGE if provider and favoured else EXACT
        out["direction"] = direction if out["kind"] == RANGE else None
        out["fallbacks"] = [f for f in fallbacks or () if _step(out, f)]
    elif allowed:
        words = standard.get("recognised_values") or {}
        out["kind"], out["limit"] = EXACT, {"values": [
            (words.get(v) or [v.replace("_", " ")])[0].title() for v in allowed]}
    else:
        out["kind"] = LEGAL_ONLY
    out["line"] = _line(out, whose)
    # room: something lies between our opening and our limit for the deal owner
    out["room"] = "value" in (out["limit"] or {}) and not _same(out)
    return out


def _step(e: dict, f: dict) -> bool:
    """A recorded fallback is shown only when it lies inside the band (never past it)."""
    return isinstance(f, dict) and within(e, {"cap_value": f.get("value"),
                                              "cap_unit": f.get("unit"),
                                              "cap_basis": f.get("basis"),
                                              "cap_party": "both"})


def within(e: dict, actual: dict | None) -> bool:
    """Whether a figure the engine read falls inside what the deal owner may agree —
    the same band `negotiation.effect_for_us` reads as Better, No change or Fallback."""
    limit, side = e.get("limit") or {}, _side(actual)
    if e["kind"] == LEGAL_ONLY or "value" not in limit or side is None \
            or side["unit"] != limit["unit"] \
            or (limit["mutual"] and side["party"] not in (None, "both")):
        return False
    v, lim = side["value"], limit["value"]
    if side["basis"] == limit["basis"]:
        if v == lim:
            return True
        return e["kind"] == RANGE and (not limit["mutual"] or side["party"] == "both") \
            and (v < lim if e["direction"] == "LOWER" else v > lim)
    # AM-301: affected-services fees never exceed total fees — one direction only
    # AM-314: past our limit only on a cap read as mutual (rule 15)
    return (e["kind"] == RANGE and e["requirement_code"] in negotiation.LOWER_CAP_IS_OURS
            and side["party"] == "both"
            and (side["basis"], limit["basis"]) in negotiation._NOT_MORE_THAN
            and v <= lim)


def _same(e: dict) -> bool:
    """Our paper already opens at our limit."""
    o, lim = e["opening"], e["limit"]
    return bool(o) and (o["value"], o["unit"], o["basis"]) == \
        (lim["value"], lim["unit"], lim["basis"])


def _line(e: dict, whose: str = "Our paper") -> str:
    """The playbook line in a salesperson's words — no codes, no engine vocabulary."""
    limit, opening = e["limit"], e["opening"]
    if e["kind"] == LEGAL_ONLY:
        return "Legal decides any change."
    if "values" in limit:
        return (f"Our position is {' or '.join(limit['values'])}. "
                "Any change goes to Legal.")
    ours = _amount(limit["value"], limit["unit"], limit["basis"])
    both = ", the same for both sides" if limit["mutual"] else ""
    start = (_amount(opening["value"], opening["unit"], opening["basis"])
             if opening else None)
    same = _same(e)
    said = [("" if not start else f"{whose} says {start}, which is also our limit."
             if same and e["kind"] == RANGE else f"{whose} says {start}.")]
    lower = e["direction"] == "LOWER"
    if e["kind"] == EXACT:
        said.append("Any change goes to Legal." if same else
                    f"You can agree to {ours}{both}. Anything else goes to Legal.")
    elif same:
        said.append(f"Anything {'more' if lower else 'less'} goes to Legal.")
    else:
        for f in e["fallbacks"]:
            said.append(f"If the client pushes back, offer "
                        f"{_amount(f['value'], f['unit'], f.get('basis'))} first.")
        said.append(f"You can agree {'up' if lower else 'down'} to {ours}{both}. "
                    f"Anything {'more' if lower else 'less'} goes to Legal.")
    return " ".join(s for s in said if s)


# ------------------------------------------------------------------ reading a Review
def from_review(db: DBSession, review: M.Review | None, *, provider: bool,
                fallbacks: dict[str, list[dict]] | None = None,
                openings: bool = True) -> list[dict[str, Any]]:
    """One entry per Finding of ``review`` (our paper); opening = its one read figure.
    ``openings=False`` (paper not provably ours, `AM-317` r4): the opening is the
    standard's own position — what we start at is ours, never the document's."""
    if review is None:
        return []
    rows: dict[str, dict] = {}
    for code, standard, rule, actual in db.execute(
            select(M.Requirement.code, M.CompanyStandardVersion.configuration,
                   M.LegalRuleVersion.configuration, M.Evaluation.actual_value)
            .select_from(M.Finding)
            .join(M.RequirementVersion,
                  M.RequirementVersion.id == M.Finding.requirement_version_id)
            .join(M.Requirement, M.Requirement.id == M.RequirementVersion.requirement_id)
            .join(M.ConfigurationSnapshotItem,
                  (M.ConfigurationSnapshotItem.snapshot_id
                   == review.configuration_snapshot_id)
                  & (M.ConfigurationSnapshotItem.requirement_version_id
                     == M.Finding.requirement_version_id))
            .join(M.CompanyStandardVersion, M.CompanyStandardVersion.id
                  == M.ConfigurationSnapshotItem.company_standard_version_id)
            .outerjoin(M.LegalRuleVersion, M.LegalRuleVersion.id
                       == M.ConfigurationSnapshotItem.legal_rule_version_id)
            .outerjoin(M.Evaluation, M.Evaluation.finding_id == M.Finding.id)
            .where(M.Finding.review_id == review.id)
            .order_by(M.Requirement.code, M.Evaluation.id)):
        row = rows.setdefault(code, {"standard": standard or {}, "rule": rule,
                                     "sides": []})
        row["sides"].append(_side(actual))
    out = []
    for code, r in rows.items():
        sides = {repr(s) for s in r["sides"]}
        opening = (r["sides"][0] if len(sides) == 1 else None) if openings \
            else _standard_side(r["standard"])
        out.append(entry(code, r["standard"], r["rule"], opening, provider=provider,
                         fallbacks=(fallbacks or {}).get(code, []),
                         whose="Our paper" if openings else "Our standard"))
    return out

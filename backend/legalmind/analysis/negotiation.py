"""Every change between two versions of ONE contract, each with who may answer it —
CLM Phase 1, "Negotiate and decide" (AB-150, owner 2026-11-02).

The client sends our contract back. This lists every difference from our previous
version once, in the returned copy's order (R1), says which differences the returned
copy did not mark as tracked changes (R2), quotes what each version's recorded Review
says about the clause (R3), and routes each to the person who may answer it (R4,
`AM-250`). Nothing here produces or changes a Finding, Classification, Rule Outcome or
Legal Decision (33.16, `AM-136` r2): a holder decides a position through the existing
decision endpoints, and an answer here is a wording choice, kept with its history in
`comparison_choices` (`AM-253`).

REUSED, NEVER DUPLICATED. The clauses are `load_clauses` (one run, page furniture out,
each row's tracked changes and pre-markup wording — the redline two-text reading of
`AM-146`/`AM-157`); comparison text is the version comparison's (33.15, whitespace
only) and Diff-Talk's (`_norm`, the clause's own number dropped); unpaired clauses are
paired by Diff-Talk's similarity (`_pair`) and moves found by its longest increasing
run; what a change does to LeapSwitch is `change_triage` (`AM-224`).

WHY NOT `compare_versions` AS IT STANDS. It keys clauses by section number and keeps
the FIRST row of each, so a change in an unnumbered sub-paragraph is only counted, and
a clause the client inserted renumbers every clause after it into a "changed" row. Here
a unit is a numbered row plus the unnumbered rows under it, paired first by exact text
(renumbering is not a change), then by number, then by similarity.

ROUTES (report §9.3, fail closed — rule 15):

* ``owner`` — positively not legal: the two texts differ only in typography (quotes,
  dashes, ligatures, spacing) and no standard measured the clause on either side.
* ``favour`` — every Finding on the returned clause is a DEVIATION the approved
  favourable rule accepted (`AM-239`), every row the client changed in it carries one,
  and code reads no reason it moves risk onto us.
* ``owner`` too (`AM-299`, manager request 2026-11-04) — every Finding on the returned
  clause is a MATCH, every row the client changed carries one, every standard that
  measured our clause still measures theirs, and code reads no reason it moves risk
  onto us: the changed text still says what our standard says.
* ``holder`` — everything else: a ratified position, a topic no standard measures, a
  clause nothing mapped, a move. Accepting it is a Legal Decision (`AM-250` r2).

WHAT IT DOES FOR US (`effect_for_us`, `AM-299`) — its own field, never a classification
or a decision (the five axes): ``POSITIVE`` "Better for us" is the favour route,
``NEUTRAL`` "No change for us" the owner's, ``NEGATIVE`` "Worse for us" the holder's.
FAIL CLOSED: anything unmeasured, unclear or not positively better or the same is
NEGATIVE ("Needs review") — never NEUTRAL. Only NEGATIVE goes to Legal.

WORDING GATE (`AM-317` r1, audit N1 2026-11-09): NEUTRAL "No change for us" is only a
change whose words are the same (`same_words`: case, punctuation, quote marks,
dashes, ligatures and spacing aside). A clause that still matches our standard but whose
words changed — a changed obligation verb ("shall endeavor to protect" -> "shall
protect"), a widened scope ("in any form"), a changed figure the engine did not see move
— goes to a holder, whatever the clause. What stays with the owner is what the engine
MEASURED: a figure moved in our favour (POSITIVE, `AM-239`/`AM-299` r3/`AM-301`) or
inside our standard (FALLBACK, `AM-306`), each answered one by one; only NEUTRAL is
accepted together (`accept_by_effect`, r2).
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.analysis import change_triage, reading
from legalmind.analysis import document_comparison as dc
from legalmind.analysis.version_comparison import ComparisonNotPossible
from legalmind.analysis.version_comparison import _normalize as _spacing
from legalmind.db import models as M
from legalmind.domain.deal_stage import final_of
from legalmind.domain.document_types import DOCUMENT_SOURCES
from legalmind.domain.enums import (
    FindingClassification,
    FindingStatus,
    MappingState,
    ReviewStatus,
)
from legalmind.evaluation.constitution_boundaries import constitution_prohibition_for
from legalmind.evaluation.user_status import ACCEPTABLE, by_finding
from legalmind.evaluation.workflow import derive_finding_status
from legalmind.extraction.parties import PROVIDER_TYPES
from legalmind.mapping.engine import Clause
from legalmind.mapping.service import load_clauses
from legalmind.security import audit
from legalmind.security.errors import SecurityError

KINDS = ("MODIFIED", "ADDED", "DELETED", "MOVED", "NEW_ANNEXURE")
OWNER, HOLDER, FAVOUR = "owner", "holder", "favour"
#: why a change went where it did — codes the screen words, never a verdict
FORMATTING_ONLY = "FORMATTING_ONLY"
IN_OUR_FAVOUR = "IN_OUR_FAVOUR"
MEASURED = "MEASURED_BY_A_STANDARD"
UNMEASURED = "NO_STANDARD_MEASURES_IT"
MOVED_CLAUSE = "MOVED"
#: `AM-307`: the Special Conditions could not be applied to a side
SPECIAL_NOT_APPLIED = "SPECIAL_CONDITIONS_NOT_APPLIED"
#: `AM-299`: the changed clause still measures MATCH against every standard it touches
STILL_MATCHES = "STILL_MATCHES_OUR_STANDARD"
#: `AM-299`: what a change does for LeapSwitch, from the route alone; anything not named
#: here is NEGATIVE (fail closed — rule 15)
POSITIVE, NEUTRAL, NEGATIVE = "POSITIVE", "NEUTRAL", "NEGATIVE"
#: `AM-306` (owner, 2026-11-04; the playbook tiers Preferred / Fallback / Escalate): the
#: client's figure is still inside our standard but on the less favourable side of our
#: own paper's figure — a concession the deal owner may make without Legal
FALLBACK = "FALLBACK"
EFFECTS = (POSITIVE, NEUTRAL, FALLBACK, NEGATIVE)
_EFFECT = {FAVOUR: POSITIVE, OWNER: NEUTRAL}
#: `AM-299` r3 (manager request 2026-11-04): a LOWER aggregate cap on liability than the
#: standard is better for us — declared from that request for these two standards, never
#: inferred for any other
LOWER_CAP_IS_OURS = frozenset({"LIABILITY-MSA-001", "LIABILITY-TOS-001"})
#: `AM-301`: fees for the affected services never exceed total fees, so N months of the
#: first is never worse for us than N months of the second. ONE direction only; never a
#: MATCH, never in `comparable_bases`, read only to decide "Better for us"
_NOT_MORE_THAN = frozenset({("FEES_PAID_FOR_AFFECTED_SERVICES", "FEES_PAID")})
#: answer -> the stored choice (`AM-285` r1: our standard and our wording beside them)
ANSWERS = {"keep_ours": "ours", "accept_theirs": "theirs",
           "use_standard": "standard", "write_wording": "custom"}
#: `AM-290`: client paper first — a row per Finding of the client's version
THEIRS_KIND = "THEIRS"
THEIRS_PREFIX = "N|THEIRS|"
#: `AM-290` r1: a row's left anchor on our template clause, namespaced
CLAUSE_ANCHOR = "clause:"
#: `AM-302`: a row compared with a blank template — its left side is that version
TEMPLATE_ANCHOR = "template:"
_SAID = {v: k for k, v in ANSWERS.items()}
#: a negotiation row key's own prefix, so Diff-Talk's writer (`PATCH /comparisons/
#: choices`, the same table) can never write — or overwrite — a negotiation answer
KEY_PREFIX = "N|"


#: a figure stays one token with its separators: "1,000" is not "1.000" (`AM-321` r2)
_TOKEN = re.compile(r"\d[\d.,]*\d|\w+")


def _tokens(text: str, number: str | None) -> list[str]:
    """The word tokens, the clause's OWN recorded number dropped when the text opens
    with it ("12.1 The Parties…"); any other leading figure is a word like the rest."""
    text = _typography(text).strip()
    if number and (label := re.match(rf"\W*{re.escape(number.rstrip('.'))}\.?(?=\s|$)",
                                     text)):
        text = text[label.end():]
    return _TOKEN.findall(text.casefold())


def same_words(before: str, after: str, before_number: str | None = None,
               after_number: str | None = None) -> bool:
    """`AM-317` r1 as corrected by `AM-321` r2, deterministic: the same words in the same
    order — case, punctuation, quote marks, dashes, ligatures and spacing aside, and each
    side's own recorded clause number (renumbering is not a change). Every figure counts,
    first cell or not ("99.9" vs "95.0", "30 days" vs "90 days", "Rs. 1,000" vs "Rs.
    1.000"); a split or joined word ("ofConfidential") is a change."""
    return _tokens(before, before_number) == _tokens(after, after_number)


def effect_for_us(route: str) -> str:
    return _EFFECT.get(route, NEGATIVE)


def _figure(actual: dict | None) -> tuple | None:
    """(value, unit, basis, party) of the one figure an Evaluation read, else None."""
    if not actual or not isinstance(actual.get("cap_value"), (int, float)):
        return None
    return (actual["cap_value"], actual.get("cap_unit"), actual.get("cap_basis"),
            actual.get("cap_party"))


def _moved(code: str, ours: tuple, theirs: tuple, direction: str | None) -> str:
    """`AM-306`: how the client's figure stands against OUR paper's (not the standard's):
    "same", "better", "worse" or "unknown" (differs, and code cannot say which way)."""
    if ours == theirs:
        return "same"
    (b, unit, basis, _), (a, unit2, basis2, _) = ours, theirs
    if code in LOWER_CAP_IS_OURS:
        direction = "LOWER"
    if direction not in ("LOWER", "HIGHER") or unit != unit2:
        return "unknown"
    up = "worse" if direction == "LOWER" else "better"
    down = "better" if up == "worse" else "worse"
    if basis == basis2:
        return "same" if a == b else (up if a > b else down)
    # AM-301, one way: affected-services fees never exceed total fees
    if direction == "LOWER" and (basis, basis2) in _NOT_MORE_THAN and a >= b:
        return "worse"
    if direction == "LOWER" and (basis2, basis) in _NOT_MORE_THAN and a <= b:
        return "better"
    return "unknown"


def effect_against_ours(route: str, why: str, before: list[dict], after: list[dict],
                        directions: dict[str, str | None]) -> str:
    """`AM-306`: the route's effect, refined by the figures on both sides. A settled
    change (owner or favour route) whose figure moved toward the client from our own
    paper's is FALLBACK; NEUTRAL stays for changes whose figures did not move (formatting,
    the same figure, a presence clause still matching); nothing here reaches NEGATIVE's
    rows or lifts a row out of NEGATIVE (rule 15)."""
    effect = effect_for_us(route)
    if effect == NEGATIVE or why == FORMATTING_ONLY:
        return effect
    was = {f["requirement_code"]: f.get("figure") for f in before}
    moves = {_moved(code, ours, f["figure"], directions.get(code))
             for f in after
             if f.get("figure") and (ours := was.get(code := f["requirement_code"]))}
    if "worse" in moves or ("unknown" in moves and route == OWNER):
        return FALLBACK
    return POSITIVE if "better" in moves else effect


def lower_cap_in_our_favour(code: str, expected: dict | None,
                            actual: dict | None) -> bool:
    """`AM-299` r3 / `AM-301`: the clause caps liability for both parties, at fewer
    months than our standard on the same basis (or at no more months on the
    affected-services fees, which never exceed total fees), same unit and scope. A cap
    limiting one party only, or whose party is not read, is never this (`AM-239` r2,
    §9; `AM-314`, rule 15); anything else is False."""
    if code not in LOWER_CAP_IS_OURS or not expected or not actual \
            or actual.get("cap_party") != "both" \
            or constitution_prohibition_for(code, actual):
        return False
    months, ours = actual.get("cap_value"), expected.get("preferred")
    if (not isinstance(months, (int, float)) or not isinstance(ours, (int, float))
            or actual.get("cap_unit") != expected.get("unit")
            or actual.get("scope") != expected.get("scope_key")):
        return False
    basis, standard = actual.get("cap_basis"), expected.get("basis")
    if basis is not None and basis == standard:
        return months < ours
    return (basis, standard) in _NOT_MORE_THAN and months <= ours


def answers(meta: dict | None) -> str | None:
    """The client's version our prepared version answers: a tracked reply's
    ``reply_to`` or a final contract's ``package_of`` (`AM-307`) — else None."""
    meta = meta or {}
    return meta.get("reply_to") or meta.get("package_of")


class VersionRoleUndeclared(SecurityError):
    """422 — P1 (owner, 2026-11-09): nobody said whose paper this version is, so it is
    neither ours nor the client's (rule 15). Nothing is compared, replied or made final
    on it until a person declares it."""

    status_code = 422
    code = "VERSION_ROLE_UNDECLARED"

    def __init__(self, version: M.DocumentVersion) -> None:
        n = version.version_number
        super().__init__(f"Nobody has said whose paper version {n} is. Say whether "
                         f"version {n} is ours or the client's before comparing, "
                         "replying or preparing the final contract.")
        self.extra = {"version_id": str(version.id), "version_number": n}


def is_declared(version: M.DocumentVersion) -> bool:
    """A person said what this version is: a ``version_role``, or the upload's
    ``source`` (whose paper)."""
    meta = version.doc_metadata or {}
    return meta.get("version_role") is not None or meta.get("source") in DOCUMENT_SOURCES


def is_ours(version: M.DocumentVersion) -> bool:
    """A version WE sent or drafted: declared Company draft, or our paper by ``source``
    — never CLIENT_MODIFIED or FINAL_SIGNED, and never an undeclared one (P1)."""
    meta = version.doc_metadata or {}
    role = meta.get("version_role")
    return role == "COMPANY_DRAFT" or (role is None
                                       and meta.get("source") == "ORGANIZATION")


def our_previous(versions: list[M.DocumentVersion],
                 after: M.DocumentVersion) -> M.DocumentVersion | None:
    """The latest version before ``after`` that is ours — what the client changed.
    Raises `VersionRoleUndeclared` for an undeclared ``after`` or one between it and
    ours: which pair the client changed is then unknown, never guessed (P1)."""
    for v in sorted(versions, key=lambda v: -v.version_number):
        if v.version_number > after.version_number:
            continue
        if not is_declared(v):
            raise VersionRoleUndeclared(v)
        if v.version_number < after.version_number and is_ours(v):
            return v
    return None

#: typography only: the same words in other quote marks, dashes or spacing (report §9.2a)
_TYPOGRAPHY = str.maketrans(
    dict.fromkeys(map(chr, (0x2018, 0x2019, 0x201A, 0x201B, 0x2032)), "'")
    | dict.fromkeys(map(chr, (0x201C, 0x201D, 0x201E, 0x2033)), '"')
    | dict.fromkeys(map(chr, (0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2212)), "-"))
_ANNEX = re.compile(r"\s*(?:SCHEDULE|ANNEXURE|ANNEX|APPENDIX|EXHIBIT)\b", re.IGNORECASE)


def _typography(text: str) -> str:
    return _spacing(unicodedata.normalize("NFKC", text or "").translate(_TYPOGRAPHY))


#: ponytail: a heading is a clause of one short line; "SERVICES" -> "SERVICES:" on every
#: heading of a returned MSA (2026-11-02) is formatting. A clause BODY's punctuation
#: stays with a holder — a comma can move a carve-out.
_HEADING_WORDS = 8


def _heading_case(before: str, after: str) -> bool:
    """A heading whose words and numbers are the same, only its case or punctuation
    differing ("1.2 Interpretation" -> "1.2 INTERPRETATION:")."""
    if any("\n" in t.strip() or len(t.split()) > _HEADING_WORDS for t in (before, after)):
        return False
    return (change_triage.code_reading(before, after)["editorial"]
            and re.findall(r"\d+", before) == re.findall(r"\d+", after))


#: a recital's joining word on its own line ("AND", "WHEREAS") is not a clause: it stays
#: with the text above it, so it is never a change row of its own (verifier item 7)
_CONNECTOR = re.compile(
    r"^(?:and|whereas|between|by and between|now,? therefore)[\s:,.]*$", re.IGNORECASE)


def _units(clauses: list[Clause]) -> list[dict[str, Any]]:
    """The clauses as negotiated: a numbered row starts one (its own number again is a
    continuation), so does an unnumbered heading or a schedule's own heading line; any
    other unnumbered row belongs to the clause above it. Text before the first is the
    opening. ``name``: only where one number belongs to two or more units (a paper that
    restarts its numbering), each such unit's OWN heading or first words (`_own_name`)
    — never a heading inferred from another row; else None. ``group``: where the
    unit's top-level number is used by two or more units, ``{key, name}`` of its parent
    — the nearest unit before it (itself included) numbered that top-level number —
    keyed by the parent's first evidence row, never its words; else None. ``parent``:
    that parent's index here (None without one)."""
    units: list[dict[str, Any]] = []
    for row in clauses:
        first = (row.content or "").strip().split("\n", 1)[0]
        part = bool(_ANNEX.match(first)) and first.isupper()
        starts = (not units or part or (row.is_heading and not row.section_number
                                        and not _CONNECTOR.match(first.strip()))
                  or (row.section_number and row.section_number != units[-1]["number"]))
        if starts:
            units.append({"number": row.section_number,
                          "heading": row.section_title or (first[:120] if part else None),
                          "page": row.page_number, "part": part, "rows": []})
        units[-1]["rows"].append(row)
    for unit in units:
        rows = unit.pop("rows")
        unit["evidence_ids"] = [str(r.evidence_id) for r in rows]
        unit["texts"] = [r.content or "" for r in rows]
        unit["text"] = "\n".join(unit["texts"])
        # each row's wording before its tracked changes; "" for text only moved or
        # inserted in under a mark — never the accepted text then
        unit["original"] = "\n".join(r.content or "" if (r.marks or {}).get("original")
                                     is None else r.marks["original"] for r in rows)
        unit["changes"] = [c for r in rows for c in (r.marks or {}).get("changes") or ()]
    numbers = Counter(_num(u["number"]) for u in units if u["number"])
    parents: dict[str, int] = {}
    for at, unit in enumerate(units):
        number = _num(unit["number"])
        unit["name"] = _own_name(unit) if number and numbers[number] > 1 else None
        if number and "." not in number:
            parents[number] = at
        p = parents.get(number.split(".")[0]) if number else None
        parent = units[p] if p is not None else None
        # the parent's index, so a deleted row can take its parent's twin's group
        unit["parent"] = p
        # keyed by the parent unit itself (its first row), never by its words
        unit["group"] = None if parent is None or numbers[_num(parent["number"])] < 2 \
            else {"key": parent["evidence_ids"][0], "name": parent["name"]}
    return units


def unit_names(clauses: list[Clause]) -> dict[str, str]:
    """{evidence_id: name} for every row of a unit whose number the paper uses twice —
    the clause's own words (`_units`), so a Points passage reads "2 — Invoicing"."""
    return {e: u["name"] for u in _units(clauses) if u["name"] for e in u["evidence_ids"]}


def review_unit_names(db: DBSession, review_id: UUID) -> dict[str, str]:
    review = db.get(M.Review, review_id)
    return unit_names(load_clauses(db, review.document_version_id)) if review else {}


def _num(number: str | None) -> str:
    return (number or "").rstrip(".")


#: how many of a unit's own first words name it when it has no heading
_NAME_WORDS = 8
_NAME_MARKUP = " \t*#\\_:.-\u2013\u2014"
_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"))


def _own_name(unit: dict) -> str | None:
    """A unit's own heading, else its first words with its number and markup left out —
    only ever this unit's text (two "2"s told apart, never a guessed parent)."""
    if (unit["heading"] or "").translate(_ZERO_WIDTH).strip():
        return unit["heading"].strip()
    text = unit["text"].translate(_ZERO_WIDTH).strip()
    number = unit["number"] or ""
    if number and text.startswith(number):
        text = text[len(number):]
    for line in text.split("\n"):          # the first line with words of its own
        words = line.strip(_NAME_MARKUP).replace("**", "").split()
        if words:
            return " ".join(words[:_NAME_WORDS]) + ("…" if len(words) > _NAME_WORDS
                                                    else "")
    return None


#: `AM-317` r3: a definition's own term — "Business Day" shall mean / means / has the
#: meaning — read from the clause's first words, any quote marks
_TERM = re.compile(r"^\W*(?:\d+(?:\.\d+)*\.?\s*)?[\"'\u2018\u2019\u201c\u201d]"
                   r"([^\"'\u2018\u2019\u201c\u201d]{1,80})[\"'\u2018\u2019\u201c\u201d]"
                   r"\s+(?:shall\s+)?(?:means?|has|have|refers?|includes?)\b",
                   re.IGNORECASE)


def _term(unit: dict) -> str | None:
    hit = _TERM.match(unit["text"])
    return " ".join(hit.group(1).casefold().split()) if hit else None


def _same_subject(a: dict, b: dict) -> bool:
    """Two clauses that share a number may be paired by it only when nothing says they
    are on different subjects: two definitions of different terms, or two headings with
    no word in common, are not one clause renumbered (`AM-317` r3)."""
    ta, tb = _term(a), _term(b)
    if ta and tb and ta != tb:
        return False
    ha, hb = (set(dc._title_words(u["heading"] or "").split()) for u in (a, b))
    return not (ha and hb and not ha & hb)


def _align(old: list[dict], new: list[dict]) -> list[tuple[int | None, int | None, bool]]:
    """(before index, after index, moved) per row in the returned copy's order; a clause
    only ours sits where we had it. Paired by exact text first (a renumbered clause is
    the same clause), then by a definition's term, then by Diff-Talk's similarity, and
    by number LAST and only where nothing says the two are on different subjects
    (`AM-317` r3, audit N2: a client who adds a definition shifts every later number).
    A clause none of these pairs is shown on one side only, never set beside another."""
    pair: dict[int, int] = {}                                   # after -> before
    by_text: dict[str, list[int]] = {}
    for i, u in enumerate(old):
        by_text.setdefault(dc._norm(u["text"]), []).append(i)
    taken: set[int] = set()
    for j, u in enumerate(new):
        free = [i for i in by_text.get(dc._norm(u["text"]), ()) if i not in taken]
        if free:
            i = next((i for i in free if old[i]["number"] == u["number"]), free[0])
            pair[j] = i
            taken.add(i)
    terms: dict[str, list[int]] = {}
    for i, u in enumerate(old):
        if i not in taken and (t := _term(u)):
            terms.setdefault(t, []).append(i)
    for j, u in enumerate(new):
        hits = terms.get(_term(u) or "", []) if j not in pair else []
        if len(hits) == 1 and hits[0] not in taken:           # one definition each
            pair[j] = hits[0]
            taken.add(hits[0])
    rest_old = [i for i in range(len(old)) if i not in taken]
    rest_new = [j for j in range(len(new)) if j not in pair]
    try:
        similar = dc._pair([{"text": old[i]["text"], "title": old[i]["heading"]}
                            for i in rest_old],
                           [{"text": new[j]["text"], "title": new[j]["heading"]}
                            for j in rest_new])
    finally:
        dc._score.cache_clear()
        dc._title_words.cache_clear()
    for b, (a, _) in similar.items():
        pair[rest_new[b]] = rest_old[a]
        taken.add(rest_old[a])
    numbered = {u["number"]: i for i, u in enumerate(old)
                if u["number"] and i not in taken}
    for j, u in enumerate(new):
        k = numbered.get(u["number"]) if j not in pair else None
        if k is not None and k not in taken and _same_subject(old[k], u):
            pair[j] = k
            taken.add(k)
    dc._title_words.cache_clear()
    # Text the returned copy MARKED as moved in (w:moveTo: none of it stood there before
    # the markup) is the move, whatever else kept its place — never the order's tie.
    # Text already inserted the same way on OUR side (our reply's own tracked insertion,
    # compared with a copy of itself) was not moved in by the returned copy.
    moved_in = {j for j in pair if new[j]["changes"] and not dc._norm(new[j]["original"])
                and dc._norm(old[pair[j]]["original"])}
    in_order = dc._longest_increasing([pair[j] for j in range(len(new))
                                       if j in pair and j not in moved_in])
    rows: list[tuple[int | None, int | None, bool]] = []
    emitted: set[int] = set()

    def ours_before(limit: int) -> None:
        for i in range(limit):
            if i not in taken and i not in emitted:
                emitted.add(i)
                rows.append((i, None, False))

    for j in range(len(new)):
        if j not in pair:
            rows.append((None, j, False))
            continue
        moved = j in moved_in or pair[j] not in in_order
        if not moved:
            ours_before(pair[j])
        rows.append((pair[j], j, moved))
    ours_before(len(old))
    return rows


#: an Evaluation a lower cap can stand on: compared (DEVIATION) or refused only on the
#: basis (UNABLE_TO_EVALUATE, affected-services fees — `AM-301`)
_CAP_READ = (FindingClassification.DEVIATION, FindingClassification.UNABLE_TO_EVALUATE)


def _findings(db: DBSession, review: M.Review | None,
              provider: bool = False) -> dict[str, list[dict]]:
    """The recorded Review's Findings by the evidence row they read — the reader word
    quoted from `by_finding` (`AM-184`), never re-derived here; with the Evaluations a
    holder decides through (`AM-250` r2). ``lower_cap_ours``: on paper where LeapSwitch
    is the provider, EVERY Evaluation of the Finding is a lower cap in our favour."""
    if review is None:
        return {}
    statuses = by_finding(db, [review.id]).get(review.id, {})
    out: dict[str, dict[str, dict]] = {}
    for finding_id, cls, evaluation_id, evidence_id, code, e_cls, expected, actual in \
            db.execute(
            select(M.Finding.id, M.Finding.classification, M.Evaluation.id,
                   M.EvaluationEvidence.evidence_id, M.Requirement.code,
                   M.Evaluation.classification, M.Evaluation.expected_value,
                   M.Evaluation.actual_value)
            .join(M.Evaluation, M.Evaluation.finding_id == M.Finding.id)
            .join(M.EvaluationEvidence,
                  M.EvaluationEvidence.evaluation_id == M.Evaluation.id)
            .join(M.RequirementVersion,
                  M.RequirementVersion.id == M.Finding.requirement_version_id)
            .join(M.Requirement, M.Requirement.id == M.RequirementVersion.requirement_id)
            .where(M.Finding.review_id == review.id)
            .order_by(M.Requirement.code, M.Evaluation.id)):
        entry = out.setdefault(str(evidence_id), {}).setdefault(str(finding_id), {
            "finding_id": str(finding_id), "requirement_code": code,
            "classification": cls.value,
            "user_status": statuses.get(finding_id, "NEEDS_DECISION"),
            "evaluation_ids": [], "lower_cap_ours": provider, "figure": _figure(actual)})
        if entry["figure"] != _figure(actual):    # two figures: none to compare (AM-306)
            entry["figure"] = None
        entry["lower_cap_ours"] = entry["lower_cap_ours"] and e_cls in _CAP_READ \
            and lower_cap_in_our_favour(code, expected, actual)
        if str(evaluation_id) not in entry["evaluation_ids"]:
            entry["evaluation_ids"].append(str(evaluation_id))
    return {e: list(f.values()) for e, f in out.items()}


def _directions(db: DBSession, review: M.Review | None) -> dict[str, str | None]:
    """Each measured standard's declared `favourable_direction`, from the Review's own
    snapshot — declared from a source, never inferred (`AM-239`)."""
    if review is None:
        return {}
    return {code: (cfg or {}).get("favourable_direction") for code, cfg in db.execute(
        select(M.Requirement.code, M.CompanyStandardVersion.configuration)
        .select_from(M.ConfigurationSnapshotItem)
        .join(M.RequirementVersion, M.RequirementVersion.id
              == M.ConfigurationSnapshotItem.requirement_version_id)
        .join(M.Requirement, M.Requirement.id == M.RequirementVersion.requirement_id)
        .join(M.CompanyStandardVersion, M.CompanyStandardVersion.id
              == M.ConfigurationSnapshotItem.company_standard_version_id)
        .where(M.ConfigurationSnapshotItem.snapshot_id
               == review.configuration_snapshot_id))}


def _public(findings: list[dict]) -> list[dict]:
    return [{k: v for k, v in f.items() if k != "figure"} for f in findings]


def _on(unit: dict | None, findings: dict[str, list[dict]]) -> list[dict]:
    seen: dict[str, dict] = {}
    for e in (unit or {}).get("evidence_ids", ()):
        for f in findings.get(e, ()):
            seen.setdefault(f["finding_id"], f)
    return list(seen.values())


def _delta(before: list[dict], after: list[dict]) -> list[dict]:
    """What changed between the two Reviews on this clause, standard by standard."""
    was = {f["requirement_code"]: f["user_status"] for f in before}
    now = {f["requirement_code"]: f["user_status"] for f in after}
    return [{"requirement_code": c, "before": was.get(c), "after": now.get(c)}
            for c in sorted(was.keys() | now.keys()) if was.get(c) != now.get(c)]


def _favoured(f: dict) -> bool:
    """Better for us: accepted in our favour under `AM-239`, or a lower cap (`AM-299`)."""
    return bool(f.get("lower_cap_ours")) or (
        f["classification"] == FindingClassification.DEVIATION.value
        and f["user_status"] == ACCEPTABLE)


def _same(f: dict) -> bool:
    """No change for us: the clause still matches our standard."""
    return (f["classification"] == FindingClassification.MATCH.value
            and f["user_status"] == ACCEPTABLE)


def _settled(f: dict) -> bool:
    return _favoured(f) or _same(f)


def _route(kind: str, old: dict | None, new: dict | None, before: list[dict],
           after: list[dict], triage: dict | None,
           found: dict[str, list[dict]]) -> tuple[str, str]:
    """Owner when positively not legal or still a MATCH; favour when better for us —
    each only when every Finding on the returned clause is better or the same, every row
    the client changed carries such a Finding (a changed sub-paragraph nothing measured
    beside a measured one is a holder's), every standard that measured our clause
    measures theirs, and code reads no risk reason (`AM-224`); else a holder (rule 15)."""
    if kind == "MOVED":
        return HOLDER, MOVED_CLAUSE
    if (kind == "MODIFIED" and not before and not after and old and new
            and (_typography(old["text"]) == _typography(new["text"])
                 or _heading_case(old["text"], new["text"]))):
        return OWNER, FORMATTING_ONLY
    measured = {f["requirement_code"] for f in after}
    if new is not None and after and not (triage or {}).get("reasons") \
            and all(map(_settled, after)) \
            and {f["requirement_code"] for f in before} <= measured:
        was = {dc._norm(t) for t in (old or {}).get("texts", ())}
        changed = [e for e, t in zip(new["evidence_ids"], new["texts"], strict=True)
                   if dc._norm(t) not in was]
        if changed and all(any(map(_settled, found.get(e, ()))) for e in changed):
            return ((FAVOUR, IN_OUR_FAVOUR) if any(map(_favoured, after))
                    else (OWNER, STILL_MATCHES))
    return HOLDER, MEASURED if before or after else UNMEASURED


def _kind(old: dict | None, new: dict | None, moved: bool) -> str | None:
    if old is None:
        assert new is not None
        return "NEW_ANNEXURE" if new["part"] else "ADDED"
    if new is None:
        return "DELETED"
    if dc._norm(old["text"]) == dc._norm(new["text"]):
        return "MOVED" if moved else None        # renumbered or unchanged: no change
    return "MODIFIED"


def _tracked(kind: str, old: dict | None, new: dict | None,
             deleted: str) -> tuple[bool, bool]:
    """(tracked, untracked) — whether the returned copy MARKED the change, and whether
    it changed our wording WITHOUT a mark (R2): its own wording before its tracked
    changes is not what we sent. A clean returned copy marks nothing, so every one of
    its changes is untracked."""
    if kind == "DELETED":
        assert old is not None
        tracked = bool(dc._norm(old["text"])) and dc._norm(old["text"]) in deleted
        return tracked, not tracked
    assert new is not None
    tracked = bool(new["changes"])
    if kind in ("ADDED", "NEW_ANNEXURE", "MOVED"):
        # moved in or inserted under a mark: none of it stood there before the markup
        return tracked, bool(dc._norm(new["original"]))
    assert old is not None
    return tracked, _spacing(new["original"]) != _spacing(old["text"])


def _clause(unit: dict) -> dict:
    return {"number": unit["number"], "heading": unit["heading"], "name": unit["name"],
            "group": unit["group"]}


def row_clause(o: dict | None, n: dict | None, old: list[dict], new: list[dict],
               twin: dict[int, int]) -> dict:
    """A row's clause: the returned copy's unit, else ours — a row only ours (deleted)
    sits in the group of its parent's twin on the returned copy (the same number), so
    one parent reads as one group whichever side its rows come from."""
    here = n or o
    assert here is not None
    p = o["parent"] if n is None and o is not None else None
    if p is not None and p in twin \
            and _num(new[twin[p]]["number"]) == _num(old[p]["number"]):
        return _clause({**here, "group": new[twin[p]]["group"]})
    return _clause(here)


def clause_label(clause: dict, heading: bool = True) -> str | None:
    """A clause in words, as the Changes tab says it (`clauseName`): "2 — Invoicing
    and Payment" for a number the paper uses twice, else "7 Fees" (or "7" without
    ``heading``) / the heading."""
    number, name = clause["number"], clause.get("name")
    if number and name:
        return f"{number} — {name}"
    return " ".join(t for t in (number, heading and clause["heading"]) if t) or None


#: `AM-299` r1 split (Batch 1, proposed): why a NEGATIVE row goes to Legal, in three
#: words — never a routing input; `effect_for_us` and the route stay as they are
WORSE, ABSENT, REVIEW, NOT_MEASURED = "WORSE", "ABSENT", "REVIEW", "NOT_MEASURED"
_MEASURED_AGAINST = (FindingClassification.DEVIATION.value,
                     FindingClassification.CONFLICT.value)
_COMPARED = (FindingClassification.MATCH.value, *_MEASURED_AGAINST)


def _measured(effect: str, kind: str, before: list[dict], after: list[dict],
              triage: dict | None) -> dict[str, str]:
    """``{"measured": …}`` on a NEGATIVE row, else nothing (omitted, never nulled).
    WORSE only where something says so: a DEVIATION or CONFLICT not accepted in our
    favour on the returned clause, an `AM-224` reason it moves risk onto us, or our
    measured clause deleted. ABSENT: the client's paper lacks the point (MISSING).
    REVIEW: a standard did measure the clause and nothing says worse (a settled deviation,
    `AM-317` r1's changed words still matching). Anything else — unable to evaluate,
    nothing measures it — is NOT_MEASURED; neither is ever "worse" (rule 15)."""
    if effect != NEGATIVE:
        return {}
    if (any(f["classification"] in _MEASURED_AGAINST and not _settled(f) for f in after)
            or (triage or {}).get("reasons") or (kind == "DELETED" and before)):
        return {"measured": WORSE}
    if kind == THEIRS_KIND and any(
            f["classification"] == FindingClassification.MISSING.value for f in after):
        return {"measured": ABSENT}
    if any(f["classification"] in _COMPARED for f in (*before, *after)):
        return {"measured": REVIEW}
    return {"measured": NOT_MEASURED}


def _side(unit: dict | None) -> dict | None:
    return {"evidence_ids": unit["evidence_ids"], "text": unit["text"]} if unit else None


def _row_key(kind: str, old: dict | None, new: dict | None) -> str:
    """Stable across reloads: our prefix, the kind and each side's first evidence row."""
    return f"{KEY_PREFIX}{kind}|{old['evidence_ids'][0] if old else ''}|" \
           f"{new['evidence_ids'][0] if new else ''}"


def _latest_review(db: DBSession, version: M.DocumentVersion) -> M.Review | None:
    return db.execute(select(M.Review).where(M.Review.document_version_id == version.id)
                      .order_by(M.Review.created_at.desc())).scalars().first()


#: `AM-307`: how a version's clauses are read. `raw_clauses` is the document's own rows;
#: `drafting.effective.effective_clauses` reads a final contract as its Special
#: Conditions vary it — passed in by the callers that may import both (the API routers
#: and the worker), never reached from here (Step 38: analysis imports no drafting).
READ_RAW, READ_APPLIED, READ_ABSENT, READ_NOT_APPLIED = (
    "NONE", "APPLIED", "ABSENT", "NOT_APPLIED")
ClauseLoader = Callable[[DBSession, UUID], tuple[list[Clause], str, "str | None"]]


def raw_clauses(db: DBSession, version_id: UUID) -> tuple[list[Clause], str, str | None]:
    return load_clauses(db, version_id), READ_RAW, None


def read_clauses(db: DBSession, version_id: UUID, loader: ClauseLoader = raw_clauses
                 ) -> tuple[list[Clause], str | None]:
    """A version's clauses as ``loader`` reads them, and — where its Special Conditions
    could not be applied or are absent — the reason (the rows then raw)."""
    clauses, status, reason = loader(db, version_id)
    return clauses, (reason if status in (READ_NOT_APPLIED, READ_ABSENT) else None)


def changes(db: DBSession, contract: M.Contract, before: M.DocumentVersion | None,
            after: M.DocumentVersion, *, legal_position: bool,
            template: dict[str, Any] | None = None,
            clause_loader: ClauseLoader = raw_clauses) -> dict[str, Any]:
    """The change list from ``before`` (our version) to ``after`` (the client's). The
    Constitution's Company Position beside a change's topic only with
    ``legal_position`` — omitted, never blanked (LEGAL-02, SEC-07). ``template`` (a
    `template_link`, ``before`` None): our side is that published template's blank,
    each placeholder matching whatever filled it (`AM-302`; `drafting.blank.link`).
    ``clause_loader`` (`AM-307`): with drafting's effective loader each side reads as its
    Special Conditions vary it; where a side's cannot be applied, both are read raw, the
    list says so (``special_conditions_not_applied``) and every row goes to a holder. The
    default reads raw (a signed copy is compared so)."""
    unapplied: list[str] = []
    if template is not None:
        ours, optional = template["clauses"], template["optional"]
        theirs = [c for c in load_clauses(db, after.id)
                  if not c.content.startswith(template["note_open"])]
    else:
        assert before is not None
        if before.contract_id != contract.id or after.contract_id != contract.id:
            raise ComparisonNotPossible("the two versions belong to different contracts")
        if before.version_number >= after.version_number:
            raise ComparisonNotPossible("compare an earlier version with a later one")
        (ours, why_ours), (theirs, why_theirs) = (
            read_clauses(db, before.id, clause_loader),
            read_clauses(db, after.id, clause_loader))
        unapplied = [w for w in (why_ours, why_theirs) if w]
        if unapplied:                  # one side cannot be applied: both read raw
            ours, theirs = load_clauses(db, before.id), load_clauses(db, after.id)
    if not ours or not theirs:
        raise ComparisonNotPossible(
            "one of these versions has no extracted text to compare — an unreadable or "
            "still-processing document cannot be compared")
    old, new = _units(ours), _units(theirs)
    if template is not None:
        as_filled(old, new, template)
    found_before = _findings(db, _latest_review(db, before)) if before else {}
    after_review = _latest_review(db, after)
    found_after = _findings(db, after_review,
                            provider=contract.contract_type in PROVIDER_TYPES)
    directions = _directions(db, after_review)
    deleted = dc._norm(" ".join(c.get("deleted") or ""
                                for u in new for c in u["changes"]))
    vendor = contract.contract_type == "VENDOR_AGREEMENT"
    aliases = reading._aliases(theirs)
    readings = change_triage.read_back(db, after.id) \
        if any(u["changes"] for u in new) else {}
    answers = answer_lines(db, contract, before, after, legal_position=legal_position)
    out: list[dict[str, Any]] = []
    aligned = _align(old, new)
    twin = {i: j for i, j, _ in aligned if i is not None and j is not None}
    for i, j, moved in aligned:
        o, n = (old[i] if i is not None else None), (new[j] if j is not None else None)
        kind = _kind(o, n, moved)
        if kind is None or (kind == "DELETED" and template is not None and o
                            and all(dc._norm(t) in optional for t in o["texts"])):
            continue       # a blank template's optional part, deleted as its note says
        here = n or o
        assert here is not None
        f_before, f_after = _on(o, found_before), _on(n, found_after)
        triage = None
        if kind != "MOVED":
            code = change_triage.code_reading(o["text"] if o else "",
                                              n["text"] if n else "", vendor, aliases)
            if not code["editorial"]:
                triage = change_triage.merged(
                    code, readings.get(n["evidence_ids"][0]) if n else None,
                    change_triage.topics_for_heading(here["heading"]))
                if not legal_position:
                    triage["topics"] = [{k: v for k, v in t.items() if k != "position"}
                                        for t in triage["topics"]]
        tracked, untracked = _tracked(kind, o, n, deleted)
        route, why = _route(kind, o, n, f_before, f_after, triage, found_after)
        if unapplied:                          # fail closed: a person reads it
            route, why = HOLDER, SPECIAL_NOT_APPLIED
        effect = effect_against_ours(route, why, f_before, f_after, directions)
        if why == STILL_MATCHES and effect == NEUTRAL \
                and not (o and n and same_words(o["text"], n["text"], o["number"],
                                                n["number"])):
            route, why, effect = HOLDER, MEASURED, NEGATIVE    # AM-317 r1: words changed
        key = _row_key(kind, o, n)
        out.append({
            "row_key": key, "kind": kind,
            # a clause both moved and reworded is MODIFIED, and says it moved
            "moved": moved and kind == "MODIFIED",
            "clause": row_clause(o, n, old, new, twin),
            "page": here["page"],
            "before": _side(o), "after": _side(n),
            "tracked": tracked, "untracked": untracked,
            "review": {"before": _public(f_before), "after": _public(f_after)},
            "review_delta": _delta(f_before, f_after),
            "triage": triage, "route": route, "route_reason": why,
            "effect_for_us": effect,
            **_measured(effect, kind, f_before, f_after, triage),
            # AM-302: an answer's left side is the template it was compared with
            **({"anchor": {
                "left_key": f"{TEMPLATE_ANCHOR}{template['template_version'].id}",
                "clause_version_id": None}} if template else {}),
            **answers(key),          # the answer here, and every round's before it
        })
    return {
        "contract_id": str(contract.id),
        "from": {"document_version_id": str(before.id),
                 "version_number": before.version_number} if before else None,
        **({"template": template["said"]} if template else {}),
        **({"special_conditions_not_applied": unapplied} if unapplied else {}),
        "to": {"document_version_id": str(after.id),
               "version_number": after.version_number},
        "summary": {"total": len(out), "untracked": sum(c["untracked"] for c in out),
                    **{k.lower(): sum(c["kind"] == k for c in out) for k in KINDS},
                    **{r: sum(c["route"] == r for c in out)
                       for r in (OWNER, HOLDER, FAVOUR)},
                    **_effects(out)},
        "changes": out,
    }


# ------------------------------------------- `AM-302`: a blank template comes back
def as_filled(old: list[dict], new: list[dict], template: dict[str, Any]) -> None:
    """A blank template's clause reads as the returned clause it matches with each
    placeholder standing for any text, and with or without the rows of an optional part
    (deleting one is what its note asks) — so filling the blank is not a change, and
    every other word still is."""
    marks = [dc._norm(f) for f in sorted(template["fields"], key=len, reverse=True)]
    split = re.compile("|".join(map(re.escape, marks))) if marks else None
    texts = {dc._norm(u["text"]): u for u in new}
    for u in old:
        kept = [t for t in u["texts"] if dc._norm(t) not in template["optional"]]
        for rows in [u["texts"], *([kept] if kept and kept != u["texts"] else [])]:
            norm = dc._norm("\n".join(rows))
            if rows is u["texts"] and (split is None or not split.search(norm)):
                continue                       # exact pairing already reads it
            parts = split.split(norm) if split else [norm]
            pattern = re.compile(".*?".join(map(re.escape, parts)), re.S)
            hit = next((n for t, n in texts.items() if pattern.fullmatch(t)), None)
            if hit is not None:
                u["text"], u["texts"], u["original"] = (hit["text"], hit["texts"],
                                                        hit["text"])
                break


def _effects(rows: list[dict]) -> dict[str, int]:
    return {e.lower(): sum(c["effect_for_us"] == e for c in rows)
            for e in EFFECTS}


def answer_lines(db: DBSession, contract: M.Contract, before: M.DocumentVersion | None,
                 after: M.DocumentVersion, *,
                 legal_position: bool = False) -> Callable[[str], dict]:
    """Each change's answer and its line across rounds (`AM-253` r2'): this pair's
    choices, preceded by the earlier rounds' answers to the same clause — found by the
    clause's evidence row: the after side of an earlier pair's row key is the before
    side of the next one. Only this ONE contract's versions are read. ``before`` None:
    client paper first (`AM-290`), its rows have no left version. Each answer carries
    its wording, standard clause and note to the client; the internal note only with
    ``legal_position`` — the KEY omitted otherwise, never nulled (`AM-285` r3, SEC-07)."""
    versions = {v.id: v.version_number for v in db.execute(
        select(M.DocumentVersion).where(M.DocumentVersion.contract_id == contract.id))
        .scalars()}
    C = M.ComparisonChoice
    rows = db.execute(
        select(C.left_version_id, C.right_version_id, C.row_key, C.choice, C.reason,
               C.version_number, C.created_at, C.wording, C.wording_sha256,
               C.clause_version_id,
               C.client_note, C.internal_note, M.User.name)
        .join(M.User, M.User.id == C.decided_by)
        .where(C.right_version_id.in_(list(versions)),
               C.left_version_id.in_(list(versions))
               | (C.left_version_id.is_(None)
                  & (C.row_key.startswith(THEIRS_PREFIX)
                     | C.left_key.startswith(TEMPLATE_ANCHOR))),
               C.row_key.startswith(KEY_PREFIX))
        .order_by(C.created_at, C.version_number)).all()
    # (right version, its evidence row) -> every answer naming that clause
    by_clause: dict[tuple[UUID | None, str], list[dict]] = {}
    for r in rows:
        clause = (r.right_version_id, r.row_key.rsplit("|", 1)[-1])
        entry = {
            "round": versions[r.right_version_id], "version_number": r.version_number,
            "answer": _SAID[r.choice], "reason": r.reason, "decided_by": r.name,
            "decided_at": r.created_at.isoformat(), "wording": r.wording,
            "wording_sha256": r.wording_sha256,
            "clause_version_id": r.clause_version_id and str(r.clause_version_id),
            "client_note": r.client_note,
            "_left": r.left_version_id, "_key": r.row_key}
        if legal_position:
            entry["internal_note"] = r.internal_note
        by_clause.setdefault(clause, []).append(entry)

    def line(key: str) -> dict:
        _, _, ours, theirs = key.split("|")
        mine = [e for e in by_clause.get((after.id, theirs), ()) if e["_key"] == key
                and e["_left"] == (before.id if before else None)]
        earlier: list[dict] = []
        left, evidence, seen = (before.id if before else None), ours, {after.id}
        while before and evidence and left not in seen:  # the same clause, a round back
            seen.add(left)
            back = by_clause.get((left, evidence), [])
            if not back:
                break
            earlier = back + earlier
            left, evidence = back[-1]["_left"], back[-1]["_key"].split("|")[2]
        public = [{k: v for k, v in e.items() if not k.startswith("_")}
                  for e in earlier + mine]
        return {"answer": public[-1] if mine else None, "history": public}
    return line


def answer_line(db: DBSession, contract: M.Contract, before: M.DocumentVersion | None,
                after: M.DocumentVersion, row_key: str, *,
                legal_position: bool = False) -> dict:
    return answer_lines(db, contract, before, after,
                        legal_position=legal_position)(row_key)


# ------------------------------------------- `AM-290`: client paper first
def _review_findings(db: DBSession, review: M.Review | None) -> list[dict]:
    """Every Finding of the Review with its Evaluations and the evidence rows they read
    (none for a MISSING clause), the reader word quoted from `by_finding`.
    ``confirmed_evidence``: the rows of the Evaluations whose recorded Mapping State
    (D-2, ``result.evaluated_facts.mapping_state``) is CONFIRMED — an UNRESOLVED or
    AMBIGUOUS mapping's rows are only its unranked candidates, and an Evaluation with
    no stamp is not confirmed (fail closed)."""
    if review is None:
        return []
    statuses = by_finding(db, [review.id]).get(review.id, {})
    out: dict[UUID, dict] = {}
    for finding_id, cls, code, evaluation_id, evidence_id, result in db.execute(
            select(M.Finding.id, M.Finding.classification, M.Requirement.code,
                   M.Evaluation.id, M.EvaluationEvidence.evidence_id,
                   M.Evaluation.result)
            .join(M.RequirementVersion,
                  M.RequirementVersion.id == M.Finding.requirement_version_id)
            .join(M.Requirement, M.Requirement.id == M.RequirementVersion.requirement_id)
            .outerjoin(M.Evaluation, M.Evaluation.finding_id == M.Finding.id)
            .outerjoin(M.EvaluationEvidence,
                       M.EvaluationEvidence.evaluation_id == M.Evaluation.id)
            .where(M.Finding.review_id == review.id)
            .order_by(M.Requirement.code, M.Evaluation.id)):
        f = out.setdefault(finding_id, {
            "finding_id": str(finding_id), "requirement_code": code,
            "classification": cls.value,
            "user_status": statuses.get(finding_id, "NEEDS_DECISION"),
            "evaluation_ids": [], "evidence_ids": [], "confirmed_evidence": []})
        confirmed = ((result or {}).get("evaluated_facts") or {}).get(
            "mapping_state") == MappingState.CONFIRMED.value
        for key, value in (("evaluation_ids", evaluation_id),
                           ("evidence_ids", evidence_id),
                           ("confirmed_evidence", evidence_id if confirmed else None)):
            if value is not None and str(value) not in f[key]:
                f[key].append(str(value))
    return list(out.values())


def realising_clause(db: DBSession, codes: set[str]) -> M.ClauseVersion | None:
    """The ONE approved clause, pinned by a PUBLISHED template, whose `realises` names
    one of ``codes`` (`AM-284` r5, `AM-252` r1–r3: chosen in code, never by a person
    typing an id). None when there is none — or more than one, which code does not
    choose between (rule 15)."""
    if not codes:
        return None
    pinned = {(p["clause_key"], p["version"])
              for tv in db.execute(select(M.TemplateVersion).where(
                  M.TemplateVersion.status == "PUBLISHED")).scalars()
              for part in [{"clauses": tv.clauses}, *tv.annexures]
              for p in part.get("clauses", [])}
    found = [cv for cv in db.execute(select(M.ClauseVersion).where(
                 M.ClauseVersion.status == "APPROVED")).scalars()
             if (cv.clause_key, cv.version) in pinned
             and codes & set(map(str, cv.realises or ()))]
    return found[0] if len(found) == 1 else None


def _holding(units: list[dict], at: dict[str, dict], evidence: list[str]) -> list[dict]:
    """The units holding any of ``evidence``, in document order."""
    mine = {id(at[e]) for e in evidence if e in at}
    return [u for u in units if id(u) in mine]


def paper_first(db: DBSession, contract: M.Contract, after: M.DocumentVersion, *,
                legal_position: bool) -> dict[str, Any]:
    """`AM-290` r1/r2: the contract's first version is the client's paper, so there is
    no wording of ours to compare: one row per Finding of its Review that is not
    Acceptable, kind THEIRS, row key ``N|THEIRS|<requirement code>|<first evidence row
    or empty>`` (stable across re-analysis — the evidence rows are the version's). Its
    left anchor is ``clause:<key>`` of the published clause realising the requirement,
    pinned by id; none — left side empty (r2)."""
    units = _units(load_clauses(db, after.id))
    at = {e: u for u in units for e in u["evidence_ids"]}
    answers = answer_lines(db, contract, None, after, legal_position=legal_position)
    out: list[dict[str, Any]] = []
    for f in _review_findings(db, _latest_review(db, after)):
        if f["user_status"] == ACCEPTABLE:
            continue
        here = _holding(units, at, f["confirmed_evidence"])
        clause = realising_clause(db, {f["requirement_code"]})
        first = f["evidence_ids"][0] if f["evidence_ids"] else ""
        key = f"{THEIRS_PREFIX}{f['requirement_code']}|{first}"
        side = {"evidence_ids": [e for u in here for e in u["evidence_ids"]],
                "text": "\n".join(u["text"] for u in here)} if here else None
        review = {k: v for k, v in f.items()
                  if k not in ("evidence_ids", "confirmed_evidence")}
        out.append({
            "row_key": key, "kind": THEIRS_KIND, "moved": False,
            "clause": _clause(here[0]) if here else
            {"number": None, "heading": None, "name": None, "group": None},
            # every clause the point was read in; none confirmed — the clauses that
            # may hold it, unranked and without a passage (nothing chose among them)
            "clauses": [_clause(u) for u in here],
            **({} if here else {"candidates": [
                _clause(u) for u in _holding(units, at, f["evidence_ids"])]}),
            "page": here[0]["page"] if here else None,
            "before": None, "after": side, "tracked": False, "untracked": False,
            "review": {"before": [], "after": [review]},
            "review_delta": [], "triage": None,
            "route": HOLDER, "route_reason": MEASURED, "effect_for_us": NEGATIVE,
            **_measured(NEGATIVE, THEIRS_KIND, [], [review], None),
            "anchor": {"left_key": f"{CLAUSE_ANCHOR}{clause.clause_key}" if clause
                       else None,
                       "clause_version_id": str(clause.id) if clause else None},
            **answers(key)})
    return {
        "contract_id": str(contract.id), "from": None,
        "to": {"document_version_id": str(after.id),
               "version_number": after.version_number},
        "summary": {"total": len(out), "untracked": 0,
                    **{k.lower(): 0 for k in KINDS}, THEIRS_KIND.lower(): len(out),
                    **{r: sum(c["route"] == r for c in out)
                       for r in (OWNER, HOLDER, FAVOUR)},
                    **_effects(out)},
        "changes": out,
    }


# ------------------------------------------- `AM-293`: nothing undecided leaves
#: a Review whose analysis has finished (anything else fails closed)
_ANALYSED = (ReviewStatus.ANALYSIS_COMPLETE, ReviewStatus.LEGAL_REVIEW,
             ReviewStatus.RESOLVED, ReviewStatus.CLOSED)
_UNDECIDED = (FindingStatus.DECISION_REQUIRED, FindingStatus.AWAITING_CLARIFICATION)


def reply_open_points(db: DBSession, version: M.DocumentVersion) -> dict | None:
    """Why our prepared reply may not be downloaded or sent yet (`AM-293` r1), or None.
    Only a COMPANY_DRAFT reply (``reply_to`` set) is gated — an ordinary upload never.
    Its latest Review must have finished its analysis (none, queued or failed fails
    closed, `AM-284` r2) and hold no undecided point."""
    meta = version.doc_metadata or {}
    ours = meta.get("version_role") == "COMPANY_DRAFT"
    if not (answers(meta) or final_of(meta)) or not ours:
        return None
    review = _latest_review(db, version)
    if review is None or review.status not in _ANALYSED:
        return {"reason": "ANALYSIS_NOT_FINISHED", "open_points": []}
    points = [{"finding_id": str(fid), "requirement_code": code}
              for fid, code in db.execute(
                  select(M.Finding.id, M.Requirement.code)
                  .join(M.RequirementVersion,
                        M.RequirementVersion.id == M.Finding.requirement_version_id)
                  .join(M.Requirement,
                        M.Requirement.id == M.RequirementVersion.requirement_id)
                  .where(M.Finding.review_id == review.id,
                         M.Finding.status.in_(_UNDECIDED))
                  .order_by(M.Requirement.code))]
    return {"reason": "UNDECIDED_POINTS", "open_points": points} if points else None


# ------------------------------------------- `AM-299` r3: carried onto our reply
def carry_acceptances(db: DBSession, review: M.Review, *,
                      request_id: str | None = None,
                      clause_loader: ClauseLoader = raw_clauses) -> int:
    """Our reply's own Review takes the deal owner's acceptances of the client's
    changes "Better for us" / "No change for us" (`AM-299` r3, amending `AM-293` r1), by
    row: a Finding of the reply still DECISION_REQUIRED, on a requirement measured on the
    accepted row, read from a reply clause whose text is the accepted row's text exactly
    (spacing and the clause number aside) — anything else stays undecided (rule 15).
    Recorded as one audit row per Finding, actor the person who accepted, with the effect
    and their reason — never a Legal Decision; the Finding's derived status then reads
    RESOLVED. A "Worse for us" change is never carried: it keeps the `AM-293` gate.
    Returns how many."""
    reply = db.get(M.DocumentVersion, review.document_version_id)
    meta = (reply.doc_metadata or {}) if reply else {}
    of = answers(meta) or final_of(meta)        # AM-318: a final copy of their version
    if reply is None or not of or meta.get("version_role") != "COMPANY_DRAFT":
        return 0
    theirs = db.get(M.DocumentVersion, UUID(of))
    if theirs is not None and not answers(meta) and (
            theirs.doc_metadata or {}).get("version_role") == "COMPANY_DRAFT":
        return 0                    # a final copy of our own version: no client round
    contract = db.get(M.Contract, review.contract_id)
    versions = list(db.execute(select(M.DocumentVersion).where(
        M.DocumentVersion.contract_id == review.contract_id)).scalars())
    try:
        before = our_previous(versions, theirs) if theirs is not None else None
    except VersionRoleUndeclared:
        return 0                    # P1: whose paper is unknown — nothing is carried
    if theirs is None or before is None or contract is None:
        return 0
    C = M.ComparisonChoice
    accepted: dict[str, list[tuple[dict, M.ComparisonChoice]]] = {}   # reply text -> rows
    for change in changes(db, contract, before, theirs, legal_position=False,
                          clause_loader=clause_loader)["changes"]:
        if change["effect_for_us"] == NEGATIVE or change["after"] is None:
            continue
        choice = db.execute(select(C).where(
            C.left_version_id == before.id, C.right_version_id == theirs.id,
            C.row_key == change["row_key"]).order_by(C.version_number.desc())
            .limit(1)).scalars().first()
        if choice is not None and choice.choice == ANSWERS["accept_theirs"]:
            accepted.setdefault(dc._norm(change["after"]["text"]), []).append(
                (change, choice))
    carried = 0
    found = _findings(db, review)
    for unit in _units(read_clauses(db, reply.id, clause_loader)[0]):
        rows = accepted.get(dc._norm(unit["text"]), [])
        if len(rows) != 1:                          # none, or two to choose between
            continue
        change, choice = rows[0]
        codes = {f["requirement_code"] for f in change["review"]["after"]}
        for f in _on(unit, found):
            finding = db.get(M.Finding, UUID(f["finding_id"]))
            if (finding is None or f["requirement_code"] not in codes
                    or finding.status is not FindingStatus.DECISION_REQUIRED):
                continue
            audit.record(db, action=audit.NEGOTIATION_ACCEPTANCE_CARRIED,
                         entity_type="finding", entity_id=finding.id,
                         actor_id=choice.decided_by, request_id=request_id,
                         after={"effect": change["effect_for_us"],
                                "reason": choice.reason,
                                "row_key": change["row_key"],
                                "answer_version": choice.version_number,
                                "from_version_id": str(theirs.id),
                                "review_id": str(review.id),
                                "requirement_code": f["requirement_code"]})
            finding.status = derive_finding_status(db, finding)
            carried += 1
    db.flush()
    return carried

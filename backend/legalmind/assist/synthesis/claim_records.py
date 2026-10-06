"""Claim units from the STRUCTURED source records — PHASE 12, `AM-92`.

    units = claim_records.units(db, source)

PHASE 12's first contracts re-parsed each source's flattened context text, and the
qualifiers that live elsewhere in a source's structure were lost with it: an entry's
"Current Legal Status: NOT YET IN FORCE", §31.14's "C. Exceptions", a standard's
governing heading, "this position"'s antecedent, a statute's proviso and item range.
The records already hold that structure:

  Legal Constitution — `assist.knowledge_items` (`AM-79`): section → provision →
      paragraph, each with its own heading (`clause`), authority and status. A unit is
      one paragraph — or one row of an entry's field table — carrying:
        heading       its provision chain ("Service Discontinuation & Material Scope
                      Changes › A. Planned Full Service Discontinuation / Retirement")
        scope         the section's Applicability ("governs ongoing, non-fixed-term
                      arrangements") and the provision's Applicable Document Types
        temporal      the entry's Current Legal Status / a commencement date
        exceptions    the text of a sibling "Exceptions" provision, in full
        referent      what "this position" / "this entry" refers to
      Purpose, Drafting Notes / illustrative clauses, Source of Truth, Status, Legal
      Validation, Applicability, STATUS lines and advisory table rows are never units.
  Statutes — `assist.statute_chunks`: a unit is one WHOLE sub-section with its items,
      provisos and Explanations, framed by the section's marginal note — so a proviso is
      never separated from its rule, nor spliced onto the next.

Every unit's `text` is the record's own words (whitespace aside); nothing is authored.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import text as sql

from legalmind import config
from legalmind.assist.knowledge import statutes as statute_corpus


@dataclass(frozen=True)
class Unit:
    text: str
    authority: str
    status: str
    heading: tuple[str, ...] = ()
    scope: tuple[str, ...] = ()
    temporal: str | None = None
    exceptions: str | None = None
    referent: str | None = None
    #: Local anaphors and what they stand for, both in the records' own words:
    #: ("that sum", "a sum payable on breach").
    antecedents: tuple[tuple[str, str], ...] = ()
    frame: str | None = None
    citation_suffix: str = ""
    order: int = 0
    extra: dict = field(default_factory=dict)


# Provision headings whose paragraphs are not claims.
_NOT_A_CLAIM = re.compile(r"^(?:purpose|source of truth|status|legal validation|drafting "
                          r"notes|illustrative|counsel)", re.I)
_APPLICABILITY = re.compile(r"^applicability\b", re.I)
_EXCEPTIONS = re.compile(r"(?:^|\W)exceptions?\b", re.I)
_MEANING = re.compile(r"^(?:acceptable|unacceptable|negotiable|approval required)", re.I)
_STATUS_LINE = re.compile(r"^\W*STATUS:", re.I)
_DOC_TYPES = re.compile(r"^\W*Applicable Document Types:\W*(.+)$", re.I)
_EVIDENCE = re.compile(r"^[\s*]*Evidence / Source:[\s*]*", re.I)
_LETTERED = re.compile(r"^[A-Z]\.\s")
# A lead-in that announces the positions below it ("The stakeholder has approved the
# following approach for …; this was originally proposed as a draft …") — provenance,
# not a claim; the lettered sub-parts that follow ARE the positions (run 9, GT-09).
_LEAD_IN = re.compile(r"\b(?:has|have) approved the following\b|\bthe following "
                      r"approach\b", re.I)
_SCOPE_OF_APPLICATION = re.compile(r"^scope of application\b", re.I)
# Antecedents outside the paragraph's own group: "matching the Scope of Application
# above" (§14), "NOT DEFINED beyond the confirmed position" (the section's topic).
_SCOPE_ABOVE = re.compile(r"scope of application above", re.I)
_CONFIRMED = re.compile(r"\bthe confirmed position\b", re.I)
# Local anaphors (§14's legal basis: "where that sum is by way of penalty", "the
# contractual amount stated above"). "that sum" resolves inside its own paragraph; a
# thing "stated above" to the last amount/value an earlier claim of the section states.
_THAT = re.compile(r"\b(?:that|such|the said) (sum|amount|fee|value)\b", re.I)
_ABOVE = re.compile(r"\bthe (?:[\w-]+ ){0,3}?(?:sum|amount|fees?|value) stated above\b",
                    re.I)
_VALUE = r"\b(?:a|an|the) (?:[\w-]+ ){0,3}?(?:sum|amount|fees?|value)\b"
_ANTECEDENT = re.compile(r"^\W*(?:this|these|such)\s+(?:position|entry|entries|section|"
                         r"rule|approach|obligations?)\b", re.I)
# A status that CHANGES what applies today — not yet in force, commencing on a date,
# repealed (`_statute`). Plain "IN FORCE" and "IN FORCE since <date/Act>" are the
# ordinary state of a current provision and qualify nothing a sentence must repeat:
# read as qualifiers they rejected A-03's correct IT Act paraphrase (PHASE 13,
# `AM-94`, narrowing `AM-92` r2).
# A dot ends the status only where it ends a sentence: "(Section 28.2.1)" was cut to
# "(Section 28" and read as the Act's s. 28 (run 9, F-05; `AM-104`).
_TEMPORAL = re.compile(r"NOT YET IN FORCE(?:[^|.]|\.(?=\S))*|commences? (?:on )?"
                       r"\d{1,2} \w+ \d{4}(?:[^|.]|\.(?=\S))*", re.I)
# Field-table rows that are advice to the reader or to Counsel, not claims.
_ADVISORY_ROWS = re.compile(r"^(?:recommended legal mind response|human / legal review|"
                            r"counsel validation|source / citation|legal source|"
                            r"current legal status)", re.I)


def units(db, source) -> list[Unit] | None:
    """The source's claim units from its records, or None when it has none (a company
    standard, a document) — the caller then reads the text as before."""
    ref = source.ref
    if ref.startswith("CONST:"):
        return _constitution(db, source.candidate.item_id)
    if ref.startswith("STAT:"):
        return _statute(db, source.candidate.item_id)
    return None


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\\", "")).strip(" *")


def _constitution(db, item_id: UUID) -> list[Unit] | None:
    schema = config.assist_schema()
    rows = db.execute(sql(f"""
        WITH hit AS (SELECT source_id, section_path FROM "{schema}".knowledge_items
                      WHERE id = :id)
        SELECT k.id, k.parent_id, k.kind, k.clause, k.content, k.authority, k.status
          FROM "{schema}".knowledge_items k, hit
         WHERE k.source_id = hit.source_id AND k.section_path = hit.section_path
         ORDER BY k.line_start"""), {"id": item_id}).all()
    if not rows:
        return None
    # The records' parent links are flat under a subsection, so a provision's GROUP is
    # read from document order: an unlettered provision opens a group, a lettered one
    # ("A. …", "B. …", "C. Exceptions") joins it. The group is what "Applicable Document
    # Types", a "C. Exceptions" list and "this position" belong to.
    # "13. Termination & Suspension" as "Section 13 (Termination & Suspension)": a
    # bare "13." ends a sentence to every splitter downstream.
    section = next((re.sub(r"^([\d.]*\d)\.?\s+(.+)$", r"Section \1 (\2)",
                           _clean(r[3] or "")) for r in rows
                    if r[2] in ("SECTION", "SUBSECTION")), None)
    heading_of: dict = {}
    group_of: dict = {}
    group_head: dict = {}
    current = None
    for r in rows:
        if r[2] != "PROVISION":
            continue
        title = _clean(r[3] or "")
        if not _LETTERED.match(title) or current is None:
            current = r[0]
            group_head[current] = title
        group_of[r[0]] = current
        heading_of[r[0]] = ((group_head[current], title) if current != r[0]
                            else (title,))
    # Section-wide scope: the Applicability paragraph ("… governs ongoing, non-fixed-term
    # arrangements").
    section_scope: list[str] = []
    scope_text = ""
    doc_types: dict = {}
    exceptions: dict = {}
    for r in rows:
        if r[2] != "PARAGRAPH":
            continue
        own = heading_of.get(r[1], ())
        if own and _SCOPE_OF_APPLICATION.match(own[-1]) and not scope_text:
            # Its governing clause, not the "particularly where: …" examples.
            scope_text = re.split(r",?\s+particularly\b|:\s|\.\s", _clean(r[4]))[0]
        if own and _APPLICABILITY.match(own[-1]):
            # Only a limit on the claims ("governs ongoing, non-fixed-term arrangements");
            # the Entity/Brand axis is C-19, recorded and not coded.
            m = re.search(r"\bgoverns ([^.;]+)", r[4])
            if m:
                section_scope.append(_clean(m.group(1)))
        m = _DOC_TYPES.match(r[4])
        if m and r[6] != "UNRATIFIED":
            doc_types[group_of.get(r[1])] = re.sub(r"\s*\(where applicable\)", "",
                                                   _clean(m.group(1)).split(". ")[0])
        if own and _EXCEPTIONS.search(own[-1]) and not _ANTECEDENT.match(r[4]) \
                and not _EVIDENCE.match(r[4]) and not _STATUS_LINE.match(r[4]):
            exceptions.setdefault(group_of.get(r[1]), []).append(_clean(r[4]))
    out: list[Unit] = []
    earlier: list[str] = []                 # the section's claims so far, in order
    for order, r in enumerate(rows):
        _id, parent, kind, _clause, content, authority, status = r
        if kind != "PARAGRAPH" or status == "UNRATIFIED":
            continue
        heading = heading_of.get(parent, ())
        if heading and (_NOT_A_CLAIM.match(heading[-1])
                        or _APPLICABILITY.match(heading[-1])):
            continue
        body = _clean(content)
        if not body or _STATUS_LINE.match(content) or _DOC_TYPES.match(content) \
                or _LEAD_IN.search(body):
            continue
        provenance = bool(_EVIDENCE.match(content))
        if provenance:
            if authority != "HISTORICAL_EXCEPTION":
                continue            # provenance of a position, not a claim
            body = _EVIDENCE.sub("", body)
        group = group_of.get(parent)
        # A historical deal inherits no current document-type scope; a lettered sub-part
        # that names its own type ("A. MSA / Customer") narrows the group's list.
        types = _own_types(doc_types.get(group), heading) \
            if authority != "HISTORICAL_EXCEPTION" else None
        scope = tuple(section_scope + ([f"{types} agreements"] if types else []))
        in_exceptions = bool(heading) and bool(_EXCEPTIONS.search(heading[-1]))
        own_exc = None if in_exceptions else " ".join(exceptions.get(group, [])) or None
        # An exceptions paragraph qualifies its GROUP's position: said alone it reads as a
        # general rule (run 9, A-01), so it names the group, like "this position" does.
        referent = (group_head.get(group) if _ANTECEDENT.match(body) or in_exceptions
                    else f"Scope of Application: {scope_text}" if scope_text and
                    _SCOPE_ABOVE.search(body)
                    else section if section and _CONFIRMED.search(body) else None)
        frame = next((h for h in reversed(heading) if _MEANING.match(h)), None)
        base = {"authority": authority, "status": status, "heading": heading,
                "scope": scope, "exceptions": own_exc, "referent": referent,
                "antecedents": _antecedents(body, earlier), "frame": frame,
                "order": order, "extra": {"provenance": True} if provenance else {}}
        earlier.append(body)
        if body.startswith("| Field |"):
            out += _field_rows(content, base)
            continue
        if body.startswith("|"):
            body = _table_rows(content)
            if not body:
                continue
        temporal = _TEMPORAL.search(body)
        out.append(Unit(text=body,
                        temporal=_clean(temporal.group(0)) if temporal else None,
                        **base))
    return out


def _own_types(listed: str | None, heading: tuple[str, ...]) -> str | None:
    """The group's document types, or only those its lettered sub-part names."""
    if not listed or len(heading) < 2:
        return listed
    names = [t.strip() for t in re.split(r",\s*(?:and\s+)?|\s+and\s+", listed)
             if t.strip()]
    own = [t for t in names if re.search(r"\b" + re.escape(
        t.split()[0] if t.endswith("Agreement") else t) + r"\b", heading[-1])]
    return ", ".join(own) if own else listed


def _antecedents(body: str, earlier: list[str]) -> tuple[tuple[str, str], ...]:
    out = []
    for m in _THAT.finditer(body):
        noun = _VALUE.replace("(?:sum|amount|fees?|value)", m.group(1))
        prior = [x.group(0) for x in re.finditer(noun + r"[^,.;\u2014]*",
                                                  body[:m.start()])]
        if prior:
            out.append((m.group(0), prior[-1].strip()))
    for m in _ABOVE.finditer(body):
        prior = [x.group(0) for p in earlier for x in re.finditer(_VALUE, p)
                 if not _ABOVE.match(x.group(0))]
        if prior:
            out.append((m.group(0), prior[-1]))
    return tuple(out)


def _field_rows(content: str, base: dict) -> list[Unit]:
    """An entry's field table, one unit per substantive row — every one carrying the
    entry's Current Legal Status (the qualifier four PHASE 12 sentences dropped)."""
    rows = {}
    for line in content.split("\n"):
        cells = [_clean(c) for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0] and not cells[0].startswith(":-") \
                and cells[0].lower() != "field":
            rows[cells[0]] = " | ".join(cells[1:])
    status = next((v for k, v in rows.items() if k.lower() == "current legal status"),
                  None)
    temporal = None
    if status:
        m = _TEMPORAL.search(status)
        temporal = _clean(m.group(0)) if m else None
    return [Unit(text=f"{k}: {v}", temporal=temporal, **base)
            for k, v in rows.items() if not _ADVISORY_ROWS.match(k)]


def _table_rows(content: str) -> str:
    lines = []
    for line in content.split("\n"):
        cells = [_clean(c) for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0] and not cells[0].startswith(":-") and \
                cells[0].lower() not in ("field", "question", "category", "business "
                                         "status", "tranche", "role"):
            lines.append(" — ".join(c for c in cells if c))
    return "; ".join(lines)


_FOOTNOTES = re.compile(r"(?mi)^\d{1,2}\.\s[^\n]*\b(?:subs\.|ins\.|rep\.|omitted|see|"
                        r"cf\.|w\.e\.f|by Act \d)[^\n]*(?:\n(?!\d{1,4}\s*$)[^\n]*)*?"
                        r"(?:\n\d{1,4}\s*$|\Z)")
# After the title's dash, a space or a footnote marker may come first: "definitions. —
# (1)", "award.— 3 [(1)" — sub-section (1) of 219 sections (DPDP ss. 1–23, Arbitration
# s. 29A's twelve months) read as a bare title and was dropped (run 9, E-04; `AM-104`).
_AFTER_DASH = r"[\u2013\u2014]+\s*(?:\d+\s*\[)?"
_SUBSECTION = re.compile(r"(?m)^\s*(?:\d+\[)?\((\d+[A-Z]?)\)\s|"
                         + _AFTER_DASH + r"\((1)\)")


def _statute(db, chunk_id: UUID) -> list[Unit] | None:
    """Whole sub-sections of the hit's section, provisos and items kept with their
    rule."""
    schema = config.assist_schema()
    rows = db.execute(sql(f"""
        WITH hit AS (SELECT statute_id, section_number FROM "{schema}".statute_chunks
                      WHERE id = :id)
        SELECT c.content, c.marginal_note, s.official_title, s.status, c.section_number
          FROM "{schema}".statute_chunks c
          JOIN "{schema}".statutes s ON s.id = c.statute_id, hit
         WHERE c.statute_id = hit.statute_id AND c.section_number = hit.section_number
         ORDER BY c.ordinal"""), {"id": chunk_id}).all()
    if not rows:
        return None
    note = _clean(rows[0][1] or "")
    # "The Companies Act, 1956 (REPEALED — …)" names "Companies Act, 1956".
    act = re.split(r"\s+[(—]", re.sub(r"^The\s+", "", _clean(rows[0][2] or "")))[0] \
        or None
    repealed = rows[0][3] == "REPEALED"
    whole = "\n".join(r[0] for r in rows)
    # Page-foot notes the extraction left mid-text ("1. As to lien … 3. Ss. 178 and
    # 178A subs. by Act 4 of 1930 …" then the page number "42"): editorial, not law.
    whole = _FOOTNOTES.sub("\n", whole)
    whole = re.sub(r"(?m)^\s*\d+\.\s+(?:Subs|Ins|Omitted|The words)\b.*$|^IndiaCode$", "",
                   whole)
    cuts = [m.start() for m in _SUBSECTION.finditer(whole)] or [0]
    if cuts[0] != 0:
        cuts.insert(0, 0)
    pieces = [whole[a:b] for a, b in zip(cuts, [*cuts[1:], len(whole)], strict=True)]
    out = []
    for order, piece in enumerate(pieces):
        body = _clean(piece)
        # …or straight after the number where the title sits in the margin ("100. (1)",
        # the Gazette print of the Income-tax Act, 1961).
        m = re.match(r"^(?:\d+\[)?\((\d+[A-Z]?)\)|^\d+[A-Z]*\.\s*\((1)\)", body) or \
            re.search(_AFTER_DASH + r"\((\d+)\)", body[:200])
        sub = next((g for g in m.groups() if g), None) if m else None
        if m and m.re.pattern.startswith(_AFTER_DASH):
            # The title before the dash is the unit's frame already; the record starts
            # at "(1)", without the print's footnote marker ("— 3 [(1) … ]" was shown
            # to readers, `AM-104`).
            body = body[m.end() - len(f"({sub})"):]
            if body.count("]") > body.count("["):
                body = re.sub(r"\]([\s.;:]*)$", r"\1", body)
        if len(body.split()) < 5 or (not m and len(pieces) > 1):
            continue            # a bare section title is not a claim
        temporal = _TEMPORAL.search(body)
        # Commencement is not in the statutory text (`AM-104`): DPDP s. 33 read as
        # operative law while the Constitution records it commencing 13 May 2027.
        starts = statute_corpus.commencement(rows[0][2], rows[0][4], sub)
        out.append(Unit(text=body, authority="PRIMARY_LAW",
                        status="REPEALED" if repealed else "CURRENT",
                        heading=(note,) if note else (), frame=note or None,
                        referent=act,          # "this Act" is the Act, named
                        temporal="REPEALED" if repealed else starts or (
                            _clean(temporal.group(0)) if temporal else None),
                        citation_suffix=f"({sub})" if sub else "", order=order))
    return out

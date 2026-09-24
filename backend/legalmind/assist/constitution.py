"""The Legal Constitution as a canonical source — roadmap §1, `AM-79` (AB-29).

The Markdown file stays the canonical document. `parse` turns it into the structured
representation beside it — sections → subsections → provisions → paragraphs — with
every line of the file landing in exactly one item (so content loss is testable, not
assumed), the Constitution's OWN numbering as `section_path` (never generated), and
authority/status read from labels the document itself uses:

  "Historical exceptions:" / "Historical evidence:" paragraphs → HISTORICAL_EXCEPTION,
      status HISTORICAL — what past signed paper said, never current policy (§31.2);
      likewise an "Evidence / Source" or ⚠ note naming a counterparty placeholder
      ("[Customer A]") — the file's header says placeholders mark historical evidence.
      A summary TABLE naming one is not history unless it follows a historical block.
  "Applicable Law / Legal Basis" provisions, §6 and §28 → SECONDARY_REFERENCE — the
      company's reading of the law, which is not the law (roadmap §1 class 6).
  §31.6a ("NOT CURRENTLY ADOPTED") → UNRATIFIED, the one carve-out `AM-73` keeps.
  Appendix H (conflict traceability) → status HISTORICAL.
  Everything else → COMPANY_CONSTITUTION, CURRENT.

Deterministic, no model, no database. `ingest` writes the result; nothing reads the
file at request time.
"""
from __future__ import annotations

import dataclasses
import datetime
import hashlib
import pathlib
import re
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session as DBSession

from legalmind import config

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
CURRENT_FILE = REPO_ROOT / "docs/02-legal-domain/LEGAL_CONSTITUTION_L1.10.md"
SUPERSEDED_FILE = REPO_ROOT / "docs/02-legal-domain/LEGAL_CONSTITUTION_L1.5.md"
SOURCE_TYPE = "COMPANY_CONSTITUTION"
TITLE = "Legal Mind — Legal Constitution"
# Adoption dates from the lock records: L1.5 by AM-43 (2026-09-08), L1.10 by AM-59.
VERSIONS = {"L1.5": datetime.date(2026, 9, 8), "L1.10": datetime.date(2026, 9, 13)}

_HEADING = re.compile(r"^(#{1,4})\s+(.*)$")
_NUMBER = re.compile(r"^(?:Section\s+)?(\d+(?:\.\d+)*[a-z]?)\.?\s+(.*)$")
_APPENDIX = re.compile(r"^(Appendix [A-Z])\b")
_LIST = re.compile(r"^(\*\s|-\s|\d+\.\s)")
_HISTORICAL = re.compile(r"historical (exceptions?|evidence)\s*:", re.I)
# The file's own header: counterparty names "cited as historical evidence" are replaced
# by these placeholders — so a placeholder IS the document marking historical paper.
_PLACEHOLDER = re.compile(r"\[(Customer [A-D]|Partner [AB]|NDA Counterparty)\]")
_LAW_HEADING = re.compile(r"applicable law|legal basis", re.I)
# ponytail: "Section N" also matches statute sections ("Section 8(5) of the DPDP Act");
# refs are kept only when they name a section this document has and are not followed
# by "(" or " of the" — a parsed-citation model is the upgrade if precision matters.
_XREF = re.compile(r"(?:Sections?|§)\s*(\d+(?:\.\d+)*[a-z]?)(?!\s*\(|\s+of\s+the)")


@dataclasses.dataclass
class Item:
    ordinal: int
    parent: int | None
    level: int
    kind: str
    section_path: str | None
    clause: str | None
    lines: list[str]
    line_start: int
    line_end: int
    authority: str = "COMPANY_CONSTITUTION"
    status: str = "CURRENT"
    cross_references: tuple[str, ...] = ()

    @property
    def content(self) -> str:
        return "\n".join(self.lines).strip()


def _clean(title: str) -> str:
    return re.sub(r"\\", "", title.replace("**", "")).strip()


def _plain(block: str) -> str:
    return re.sub(r"^[\s*_⚠]+", "", block)


def parse(markdown: str) -> list[Item]:
    lines = markdown.split("\n")
    items = [Item(0, None, 0, "DOCUMENT", None, TITLE, [], 1, len(lines))]
    stack = [0]                                  # heading items, by level
    current_para: int | None = None
    blank_before = True
    for n, line in enumerate(lines, 1):
        m = _HEADING.match(line)
        if m:
            level, title = len(m.group(1)), _clean(m.group(2))
            while items[stack[-1]].level >= level:
                stack.pop()
            parent = items[stack[-1]]
            num = _NUMBER.match(title)
            app = _APPENDIX.match(title)
            path = num.group(1) if num else app.group(1) if app else parent.section_path
            kind = {1: "SECTION", 2: "SUBSECTION"}.get(level, "PROVISION")
            items.append(Item(len(items), parent.ordinal, level, kind, path, title,
                              [], n, n))
            stack.append(len(items) - 1)
            current_para = None
            continue
        if not line.strip():
            blank_before = True
            continue
        if len(items) == 1:                      # front matter belongs to the document
            items[0].lines.append(line)
            continue
        # A list item after a blank line CONTINUES its paragraph, so a
        # rule's conditions stay attached to it (roadmap §3: "rules, exceptions, and
        # conditions remain connected").
        if current_para is not None and (not blank_before or _LIST.match(line.lstrip())):
            items[current_para].lines.append(line)
            items[current_para].line_end = n
        else:
            head = items[stack[-1]]
            items.append(Item(len(items), head.ordinal, head.level + 1, "PARAGRAPH",
                              head.section_path, None, [line], n, n))
            current_para = len(items) - 1
        blank_before = False
    _classify(items)
    return items


def _ancestors(items: list[Item], item: Item):
    while item.parent is not None:
        item = items[item.parent]
        yield item


def _classify(items: list[Item]) -> None:
    paths = {i.section_path for i in items if i.section_path}
    previous_historical = False
    for item in items:
        chain = [item, *_ancestors(items, item)]
        top = next((a for a in chain if a.kind == "SECTION"), None)
        if any("NOT CURRENTLY ADOPTED" in (a.clause or "") for a in chain):
            item.status = "UNRATIFIED"
        elif any((a.section_path or "") == "Appendix H" for a in chain):
            item.status = "HISTORICAL"
        if item.kind == "PARAGRAPH":
            text_ = _plain(item.content)
            table = text_.startswith("|")
            # A summary TABLE may name a placeholder in one row among current
            # positions; only a table that belongs to a historical paragraph is history.
            note = text_.startswith("Evidence / Source") or "⚠" in item.content[:6]
            historical = (previous_historical and table) or (not table and bool(
                _HISTORICAL.search(text_) or (note and _PLACEHOLDER.search(text_))))
            previous_historical = historical
            if historical:
                item.authority = "HISTORICAL_EXCEPTION"
                if item.status != "UNRATIFIED":          # the carve-out always wins
                    item.status = "HISTORICAL"
                continue
        law_heading = any(_LAW_HEADING.search(a.clause or "")
                          for a in chain if a.kind == "PROVISION")
        if law_heading or (top and top.section_path in ("6", "28")):
            item.authority = "SECONDARY_REFERENCE"
        refs = {r for r in _XREF.findall(item.content) if r in paths}
        item.cross_references = tuple(sorted(refs - {item.section_path}))


def ingest(db: DBSession) -> dict:
    """Write both versions' source rows and the current version's items. Idempotent:
    an unchanged file (same SHA-256) is left alone; a changed one replaces its items."""
    schema = config.assist_schema()
    body = CURRENT_FILE.read_text()
    sha = hashlib.sha256(body.encode()).hexdigest()
    old_id = _source(db, schema, "L1.5", "SUPERSEDED", SUPERSEDED_FILE, None,
                     effective_to=VERSIONS["L1.10"])
    row = db.execute(text(
        f'SELECT id, file_sha256 FROM "{schema}".knowledge_sources '
        "WHERE source_type = :t AND version = 'L1.10'"), {"t": SOURCE_TYPE}).first()
    if row and row[1] == sha:
        return {"source_id": str(row[0]), "changed": False}
    if row:
        db.execute(text(f'DELETE FROM "{schema}".knowledge_sources WHERE id = :i'),
                   {"i": row[0]})
    source_id = _source(db, schema, "L1.10", "CURRENT", CURRENT_FILE, sha,
                        supersedes=old_id)
    items = parse(body)
    ids = [uuid.uuid4() for _ in items]
    for item in items:
        db.execute(text(f"""
            INSERT INTO "{schema}".knowledge_items
              (id, source_id, parent_id, ordinal, kind, section_path, clause, content,
               authority, status, cross_references, line_start, line_end)
            VALUES (:id, :s, :p, :o, :k, :sp, :c, :ct, :a, :st, :x, :ls, :le)"""), {
            "id": ids[item.ordinal], "s": source_id,
            "p": ids[item.parent] if item.parent is not None else None,
            "o": item.ordinal, "k": item.kind, "sp": item.section_path, "c": item.clause,
            "ct": item.content, "a": item.authority, "st": item.status,
            "x": list(item.cross_references), "ls": item.line_start, "le": item.line_end})
    return {"source_id": str(source_id), "changed": True, "items": len(items)}


def _source(db, schema, version, status, path, sha, supersedes=None, effective_to=None):
    existing = db.execute(text(
        f'SELECT id FROM "{schema}".knowledge_sources '
        "WHERE source_type = :t AND version = :v"),
        {"t": SOURCE_TYPE, "v": version}).scalar()
    if existing:
        return existing
    new_id = uuid.uuid4()
    db.execute(text(f"""
        INSERT INTO "{schema}".knowledge_sources
          (id, source_type, title, version, status, authority, jurisdiction,
           effective_from, effective_to, supersedes_id, source_file, file_sha256)
        VALUES (:id, :t, :ti, :v, :st, 'COMPANY_CONSTITUTION', 'IN', :ef, :et, :sup, :f,
                :sha)"""),
        {"id": new_id, "t": SOURCE_TYPE, "ti": TITLE, "v": version, "st": status,
         "ef": VERSIONS[version], "et": effective_to, "sup": supersedes,
         "f": str(path.relative_to(REPO_ROOT)), "sha": sha})
    return new_id


def item_for_section(db: DBSession, section: str):
    """The current Constitution's heading item for a section path — how a ratified
    standard's `configuration.constitution.section` points back to its source and
    surrounding context (roadmap §1). None when the section does not exist."""
    schema = config.assist_schema()
    return db.execute(text(f"""
        SELECT i.id, i.clause FROM "{schema}".knowledge_items i
          JOIN "{schema}".knowledge_sources s ON s.id = i.source_id
         WHERE s.source_type = :t AND s.status = 'CURRENT' AND i.section_path = :p
           AND i.kind <> 'PARAGRAPH'
         ORDER BY i.ordinal LIMIT 1"""), {"t": SOURCE_TYPE, "p": section}).first()

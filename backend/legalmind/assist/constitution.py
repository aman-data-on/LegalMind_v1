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
_CURRENT_VERSION = "L1.10"

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
    breadcrumb: str = ""

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
    for item in items:
        item.breadcrumb = _breadcrumb(items, item)


# Retrieval text says what a passage IS, from metadata already on the item — never
# new content (roadmap §3: "improves retrieval without changing the source text").
_AUTHORITY_LABEL = {"HISTORICAL_EXCEPTION": "historical evidence, not current policy",
                    "SECONDARY_REFERENCE": "the company's reading of the law"}


def _breadcrumb(items: list[Item], item: Item) -> str:
    heads = [a.clause for a in reversed([item, *_ancestors(items, item)])
             if a.clause and a.kind != "DOCUMENT"]
    label = _AUTHORITY_LABEL.get(item.authority)
    return " · ".join([f"Legal Constitution {_CURRENT_VERSION}", *heads,
                       *([label] if label else [])])


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
               authority, status, cross_references, line_start, line_end, breadcrumb)
            VALUES (:id, :s, :p, :o, :k, :sp, :c, :ct, :a, :st, :x, :ls, :le, :b)"""), {
            "id": ids[item.ordinal], "s": source_id,
            "p": ids[item.parent] if item.parent is not None else None,
            "o": item.ordinal, "k": item.kind, "sp": item.section_path, "c": item.clause,
            "ct": item.content, "a": item.authority, "st": item.status,
            "x": list(item.cross_references), "ls": item.line_start, "le": item.line_end,
            "b": item.breadcrumb})
    from legalmind.assist import store
    embedded = store.embed_into(
        db, table="knowledge_item_embeddings", fk="knowledge_item_id",
        rows=[(ids[i.ordinal], f"{i.breadcrumb}\n{i.content}") for i in items
              if i.kind == "PARAGRAPH" and i.status != "UNRATIFIED"])
    return {"source_id": str(source_id), "changed": True, "items": len(items),
            "embedded": embedded}


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


# ---------------------------------------------------------------------------------
# Retrieval over the child records — roadmap PHASE 3 (`AM-82`)
# ---------------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class ConstitutionHit:
    item_id: uuid.UUID
    parent_id: uuid.UUID | None
    section_path: str | None
    breadcrumb: str
    content: str
    authority: str
    status: str
    score: float


CANDIDATES = 100
_TSQ = "to_tsquery('english', (SELECT array_to_string(lex, ' | ') FROM q))"
# Length-normalised rank (normalization 1 = divide by 1 + log(length)), not a raw
# count of shared words: by count, the §27 Counsel checklist TABLE outranked §14 for
# an early-exit question because one long table mentions nearly everything. Measured
# on the 41 Constitution slots of the PHASE 0 benchmark (2026-09-24, corrected gold),
# with vectors: r@1 0.707 → 0.732, r@3 0.878 → 0.902, MRR 0.798 → 0.822, r@10 equal;
# lexical only (no model): r@1 0.244 → 0.488, MRR 0.445 → 0.645.
LEXICAL_ORDER = f"ts_rank(i.content_tsv, {_TSQ}, 1) DESC"


def search(db: DBSession, *, query: str, permissions: frozenset[str], limit: int = 6,
           embed_query=None) -> list[ConstitutionHit]:
    """Hybrid retrieval over the Constitution's PARAGRAPH records (the children) of
    the CURRENT version, authorized inside the function (`AM-79` r2). Lexical (shared
    lexemes over breadcrumb + text) and vector lists are fused by reciprocal rank,
    then collapsed to the best child per parent — so one provision's six paragraphs
    cannot take every slot (roadmap §3 exit). UNRATIFIED text is never returned;
    HISTORICAL text is, carrying its status, for the evidence layer to label."""
    from legalmind.assist import calibration, embedding_runtime, store

    if not can_search(permissions) or not (query or "").strip():
        return []
    schema = config.assist_schema()
    scope = f"""JOIN "{schema}".knowledge_sources s ON s.id = i.source_id
       WHERE s.source_type = '{SOURCE_TYPE}' AND s.status = 'CURRENT'
         AND i.kind = 'PARAGRAPH' AND i.status <> 'UNRATIFIED'"""
    cols = ("i.id, i.parent_id, i.section_path, i.breadcrumb, i.content, i.authority, "
            "i.status")
    floor = 2 if len(query.split()) > 1 else 1
    lexical = [r for r in db.execute(text(f"""
        WITH q AS (SELECT tsvector_to_array(to_tsvector('english', :q)) AS lex)
        SELECT {cols}, (SELECT count(*) FROM q, unnest(tsvector_to_array(i.content_tsv)) l
                         WHERE l = ANY(q.lex)) AS matched
          FROM "{schema}".knowledge_items i {scope}
         ORDER BY {LEXICAL_ORDER}, i.ordinal
         LIMIT :n"""), {"q": query, "n": CANDIDATES}).all() if r.matched >= floor]
    vector: list = []
    embedded = (embed_query or embedding_runtime.embed_query)(query)
    if embedded is not None:
        op = f'OPERATOR("{store.vector_schema(db)}".<=>)'
        vtype = store.vector_type(db)
        literal = "[" + ",".join(f"{x:.6f}" for x in embedded[0]) + "]"
        vector = list(db.execute(text(f"""
            SELECT {cols} FROM "{schema}".knowledge_item_embeddings e
              JOIN "{schema}".knowledge_items i ON i.id = e.knowledge_item_id {scope}
             ORDER BY e.embedding {op} CAST(:v AS {vtype}), i.ordinal
             LIMIT :n"""), {"v": literal, "n": CANDIDATES}).all())
    fused: dict = {}
    rows: dict = {}
    for ranked in (lexical, vector):
        for rank, r in enumerate(ranked, start=1):
            fused[r.id] = fused.get(r.id, 0.0) + 1 / (calibration.RRF_K + rank)
            rows.setdefault(r.id, r)
    hits, parents = [], set()
    for item_id in sorted(fused, key=lambda i: -fused[i]):
        r = rows[item_id]
        if r.parent_id in parents:
            continue
        parents.add(r.parent_id)
        hits.append(ConstitutionHit(r.id, r.parent_id, r.section_path, r.breadcrumb,
                                    r.content, r.authority, r.status, fused[item_id]))
        if len(hits) == limit:
            break
    return hits


def can_search(permissions: frozenset[str]) -> bool:
    from legalmind.assist import positions
    return positions.can_read(permissions)


def expand(db: DBSession, item_id: uuid.UUID, *, max_chars: int = 4000) -> str:
    """The parent context of a retrieved child: its NUMBERED section or subsection —
    the unit the Constitution states a position in (§14 is position + legal basis +
    system rule + validation; §31.2 is position + historical exceptions). Every
    paragraph under it, in document order, each provision's heading kept, and every
    paragraph that is not current company policy labelled with what it is, so the
    company's reading of the law and past signed paper can never read as policy.
    Windowed around the hit when longer than `max_chars`; the hit is always whole."""
    schema = config.assist_schema()
    rows = db.execute(text(f"""
        WITH RECURSIVE up AS (
            SELECT id, parent_id, kind, 0 AS depth FROM "{schema}".knowledge_items
             WHERE id = :i
            UNION ALL
            SELECT k.id, k.parent_id, k.kind, up.depth + 1
              FROM "{schema}".knowledge_items k JOIN up ON k.id = up.parent_id),
        anchor AS (SELECT id FROM up WHERE kind IN ('SECTION', 'SUBSECTION')
                    ORDER BY depth LIMIT 1),
        down AS (
            SELECT k.* FROM "{schema}".knowledge_items k
             WHERE k.id = (SELECT id FROM anchor)
            UNION ALL
            SELECT k.* FROM "{schema}".knowledge_items k
              JOIN down ON k.parent_id = down.id)
        SELECT id, kind, clause, content, authority, status, breadcrumb, id = :i AS hit
          FROM down WHERE status <> 'UNRATIFIED' ORDER BY ordinal"""),
        {"i": item_id}).all()
    if not any(r.hit for r in rows):
        return ""
    parts: list[str] = []
    hit_at = 0
    for r in rows:
        if r.kind == "PROVISION" and r.clause:
            parts.append(f"{r.clause}:")
        elif r.kind == "PARAGRAPH":
            if r.hit:
                hit_at = len(parts)
            policy = r.authority == "COMPANY_CONSTITUTION" and r.status == "CURRENT"
            label = None if policy else _AUTHORITY_LABEL.get(r.authority,
                                                             r.status.lower())
            parts.append(f"[{label}] {r.content}" if label else r.content)
    lo = hi = hit_at
    size = len(parts[hit_at])
    while True:
        grew = False
        if hi + 1 < len(parts) and size + len(parts[hi + 1]) <= max_chars:
            hi, size, grew = hi + 1, size + len(parts[hi + 1]), True
        if lo > 0 and size + len(parts[lo - 1]) <= max_chars:
            lo, size, grew = lo - 1, size + len(parts[lo - 1]), True
        if not grew:
            break
    head = next(r for r in rows if r.kind in ("SECTION", "SUBSECTION"))
    crumb = f"Legal Constitution {_CURRENT_VERSION} · {head.clause}"
    return crumb + "\n" + "\n\n".join(parts[lo:hi + 1])

"""What the client changed in a marked-up contract, clause by clause (owner, 2026-10-27:
"his legal team underlined a lot of statements and added lines … they do not catch").

The reader already keeps every tracked change on its evidence row (`AM-146`/`AM-157`:
``metadata.revision`` holds the original wording and each change). Nothing showed them:
a review measured the proposed text against our standards and a change no standard
covers fell silently into "clauses no standard covers". This lists every change, in the
document's order, grouped by its top-level section, and says for each whether one of
our standards measured that clause — naming the finding — or no standard covers it, so
a person reads it. It judges nothing itself: a change is shown, never classified (rule
7), and it is never a Finding (REC-02's shape: a document-level observation).
"""
from __future__ import annotations

from typing import Any

from legalmind.mapping.engine import Clause


def _kind(change: dict[str, str]) -> str:
    # a reader's words, not a word processor's (owner, 2026-10-27: plain language)
    if change.get("inserted") and change.get("deleted"):
        return "Changed"
    return "Added" if change.get("inserted") else "Removed"


def client_changes(clauses: list[Clause],
                   measured: dict[str, list[str]]) -> dict[str, Any] | None:
    """Every tracked change of the document, grouped by top-level section.

    ``clauses``: the review's clauses as `load_clauses` reads them — the one run that
    IS the document. ``measured``: evidence id → the names of the findings that read
    that row. The reviewer's comments come with their clause (``notes``), never as its
    text. ``None`` when the document carries neither — an unmarked contract shows
    nothing."""
    sections: list[dict[str, Any]] = []
    clause: str | None = None
    heading: dict[str, str] = {}                # a top-level number → its own heading
    for row in clauses:
        if row.section_number:      # an unnumbered row belongs to the clause above it
            clause = row.section_number
            if "." not in clause and row.section_title:
                heading[clause] = row.section_title
        if not row.marks:
            continue
        revision, notes = {"changes": row.marks["changes"]}, row.marks["comments"]
        top = (clause or "").split(".")[0] or None
        if not sections or sections[-1]["section"] != top:
            sections.append({"section": top, "title": heading.get(top or ""),
                             "page": row.page_number, "changes": [], "notes": [],
                             "measured_by": []})
        group = sections[-1]
        by = measured.get(str(row.evidence_id), [])
        group["measured_by"] += [n for n in by if n not in group["measured_by"]]
        group["notes"] += [{"clause": clause, "author": n.get("author") or "",
                            "text": n["text"]} for n in notes]
        for change in revision.get("changes") or ():
            group["changes"].append({
                "clause": clause, "page": row.page_number, "kind": _kind(change),
                "removed": change.get("deleted") or "",
                "added": change.get("inserted") or "", "measured_by": by})
    if not sections:
        return None
    changed = {c["clause"] for s in sections for c in s["changes"]}
    covered = {c["clause"] for s in sections for c in s["changes"] if c["measured_by"]}
    return {"sections": sections,
            "changes": sum(len(s["changes"]) for s in sections),
            "clauses": len(changed), "measured": len(covered),
            "unmeasured": len(changed - covered),
            "notes": sum(len(s["notes"]) for s in sections)}

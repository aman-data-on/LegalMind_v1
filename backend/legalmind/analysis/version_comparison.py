"""Deterministic clause-level version comparison — locked 33.15, 33.16, PROD-04.

Locked 33.15 asks for exactly this and says how: *"This is **not LLM/RAG**. It can
be done using deterministic document/section comparison."* Locked PROD-04 puts
`compare` in an ordinary User's hands, and rules 18/19 of Step 33 bound it:
deterministic comparison MAY identify changed clauses, and comparison **does not
itself constitute a Legal Decision**.

33.16 is the line this module must not cross. It may say:

    Clause 17.2 changed:  "Unlimited"  ->  "12 months"

It may never say, or let a caller infer, that the change is acceptable,
unacceptable, approved or rejected. So nothing here produces a Finding, a
Classification, a Rule Outcome or a Mapping State, nothing writes to any legal
table, and the payload carries no verdict field of any kind. Where a Finding
already exists for a changed clause it is REPORTED alongside — the reader gets to
see that the engine has something to say about that clause — but the Finding is
the engine's, made against a Company Standard, and this module only quotes it.

WHY SECTION NUMBER IS THE KEY. Locked 34.12 preserves the document's own clause
numbering and never generates one, so `section_number` is the one identifier both
versions genuinely share. Matching on it is a fact about the documents; matching
on title similarity or text distance would be an inference, and a wrong pairing
would put two unrelated clauses side by side under a heading that says "changed".

WHAT HAPPENS TO UNNUMBERED TEXT. Plenty of real evidence rows have no section
number — a recital, a signature block, an OCR fragment. Those are matched only by
EXACT normalized text (so unchanged boilerplate stays quiet), and whatever is left
is reported as a count of added/removed unnumbered passages rather than paired up
by guesswork. A comparison that invents pairings is worse than one that admits
what it cannot align.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M

#: How much of a clause the payload quotes. Long enough to read the change,
#: short enough that a comparison is not a second copy of the document; matches
#: the report's own unmatched-provision convention (240).
EXCERPT_CHARS = 240

#: How much of the window sits BEFORE the point the two versions diverge, when
#: the excerpt has to be centred on a difference rather than started at the top
#: of the clause. Enough lead-in to read the sentence the change sits in.
EXCERPT_LEAD = 80


class ComparisonNotPossible(Exception):
    """Raised when the two versions cannot be compared as asked."""


@dataclass
class ClauseChange:
    status: str                     # ADDED · REMOVED · CHANGED · UNCHANGED
    section_number: str | None
    section_title: str | None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    findings: list[dict[str, Any]] = field(default_factory=list)


def _normalize(text: str) -> str:
    """Whitespace-insensitive comparison text.

    Deliberately nothing more. Case, punctuation and wording are exactly what a
    reader is comparing, so folding any of them would hide a real change; only
    whitespace is normalized, because a re-flowed paragraph is not an amendment
    (the same reasoning `normalize_text` applies at extraction).
    """
    return re.sub(r"\s+", " ", text or "").strip()


def _first_difference(before: str, after: str) -> int:
    """Index of the first character at which two clause texts diverge.

    Plain prefix scan, on the NORMALIZED texts' shared prefix length mapped back
    to nothing clever — the caller only needs somewhere honest to centre a
    window, not an alignment. Returns 0 when one text is a prefix of the other,
    which is the case where the start is already the right place to look.
    """
    limit = min(len(before), len(after))
    for i in range(limit):
        if before[i] != after[i]:
            return i
    return 0


def _side(row: M.DocumentEvidence, focus: int = 0) -> dict[str, Any]:
    """One version's text, windowed around `focus`.

    WHY A WINDOW AND NOT A PREFIX. A prefix hides the change: a clause whose
    wording differs at character 900 renders as two identical-looking excerpts
    under a heading that says "wording changed", which is worse than showing
    nothing — it invites the reader to conclude the difference is cosmetic. So
    the excerpt is centred on where the two versions actually diverge, and it
    says when it has cut text off either end, because an excerpt that hides its
    own truncation is making a claim about completeness it cannot support.
    """
    content = row.content or ""
    start = 0 if focus <= EXCERPT_CHARS - EXCERPT_LEAD else focus - EXCERPT_LEAD
    excerpt = content[start:start + EXCERPT_CHARS]
    return {
        "evidence_id": str(row.id),
        "page_number": row.page_number,
        "excerpt": excerpt,
        "truncated_start": start > 0,
        "truncated_end": start + EXCERPT_CHARS < len(content),
    }


def _findings_by_section(db: DBSession, review_id: UUID | None) -> dict[str, list[dict]]:
    """Findings on the newer version, indexed by the section their evidence sits in.

    Reported, never computed: the classification is the engine's own value from
    the Review that ran against a pinned configuration snapshot. This function
    only says WHERE each existing Finding lands, so the reader can see that a
    clause which changed is also a clause the engine has an opinion about.
    """
    if review_id is None:
        return {}
    rows = db.execute(
        select(M.Finding, M.DocumentEvidence.section_number, M.Requirement.code)
        .join(M.Evaluation, M.Evaluation.finding_id == M.Finding.id)
        .join(M.EvaluationEvidence,
              M.EvaluationEvidence.evaluation_id == M.Evaluation.id)
        .join(M.DocumentEvidence,
              M.DocumentEvidence.id == M.EvaluationEvidence.evidence_id)
        # The Requirement's own code, joined rather than lazily walked: this runs
        # once per comparison and must not become a per-finding query.
        .join(M.RequirementVersion,
              M.RequirementVersion.id == M.Finding.requirement_version_id)
        .join(M.Requirement, M.Requirement.id == M.RequirementVersion.requirement_id)
        .where(M.Finding.review_id == review_id)
    ).all()
    index: dict[str, list[dict]] = {}
    for finding, section, requirement_code in rows:
        if not section:
            continue
        entry = {
            "finding_id": str(finding.id),
            "classification": finding.classification.value,
            "requirement_code": requirement_code,
        }
        bucket = index.setdefault(section, [])
        if entry not in bucket:
            bucket.append(entry)
    return index


def compare_versions(db: DBSession, before: M.DocumentVersion,
                     after: M.DocumentVersion) -> dict[str, Any]:
    """Compare two versions of ONE contract, clause by clause.

    Raises `ComparisonNotPossible` when the pair is not comparable — different
    contracts, or the same version twice. Both are caller errors rather than
    empty results, because silently returning "no changes" for two unrelated
    documents would be the most misleading answer available.
    """
    if before.contract_id != after.contract_id:
        raise ComparisonNotPossible(
            "the two versions belong to different contracts")
    if before.id == after.id:
        raise ComparisonNotPossible("a version cannot be compared with itself")

    def evidence(version: M.DocumentVersion) -> list[M.DocumentEvidence]:
        return list(db.execute(
            select(M.DocumentEvidence)
            .where(M.DocumentEvidence.document_version_id == version.id)
            .order_by(M.DocumentEvidence.page_number.asc().nulls_last(),
                      M.DocumentEvidence.start_offset.asc().nulls_last(),
                      M.DocumentEvidence.id.asc())
        ).scalars().all())

    old_rows, new_rows = evidence(before), evidence(after)
    if not old_rows or not new_rows:
        raise ComparisonNotPossible(
            "one of these versions has no extracted text to compare — "
            "an unreadable or still-processing document cannot be compared")

    # The newest Review of the newer version, for reporting existing Findings.
    review = db.execute(
        select(M.Review).where(M.Review.document_version_id == after.id)
        .order_by(M.Review.created_at.desc())
    ).scalars().first()
    findings = _findings_by_section(db, review.id if review else None)

    def numbered(rows: list[M.DocumentEvidence]) -> dict[str, M.DocumentEvidence]:
        # First row wins for a repeated number: reading order is the document's
        # own, so the first occurrence is the clause and later ones are
        # cross-references to it.
        out: dict[str, M.DocumentEvidence] = {}
        for row in rows:
            if row.section_number and row.section_number not in out:
                out[row.section_number] = row
        return out

    old_by_section, new_by_section = numbered(old_rows), numbered(new_rows)
    changes: list[ClauseChange] = []

    for section in sorted(set(old_by_section) | set(new_by_section),
                          key=_section_sort_key):
        old_row = old_by_section.get(section)
        new_row = new_by_section.get(section)
        if old_row is not None and new_row is not None:
            same = _normalize(old_row.content) == _normalize(new_row.content)
            # Both sides are windowed on the SAME divergence point, so the two
            # excerpts stay readable against each other rather than drifting.
            focus = 0 if same else _first_difference(old_row.content or "",
                                                     new_row.content or "")
            changes.append(ClauseChange(
                status="UNCHANGED" if same else "CHANGED",
                section_number=section,
                section_title=new_row.section_title or old_row.section_title,
                before=_side(old_row, focus), after=_side(new_row, focus),
                findings=[] if same else findings.get(section, []),
            ))
        elif new_row is not None:
            changes.append(ClauseChange(
                status="ADDED", section_number=section,
                section_title=new_row.section_title,
                after=_side(new_row), findings=findings.get(section, [])))
        else:
            assert old_row is not None
            changes.append(ClauseChange(
                status="REMOVED", section_number=section,
                section_title=old_row.section_title, before=_side(old_row)))

    # Unnumbered text: exact-match only, then counted. See the module note.
    old_free = [r for r in old_rows if not r.section_number]
    new_free = [r for r in new_rows if not r.section_number]
    old_texts = {_normalize(r.content) for r in old_free}
    new_texts = {_normalize(r.content) for r in new_free}
    unnumbered = {
        "unchanged": len(old_texts & new_texts),
        "added": len(new_texts - old_texts),
        "removed": len(old_texts - new_texts),
    }

    summary = {status: sum(1 for c in changes if c.status == status)
               for status in ("ADDED", "REMOVED", "CHANGED", "UNCHANGED")}

    return {
        "before": {"document_version_id": str(before.id),
                   "version_number": before.version_number},
        "after": {"document_version_id": str(after.id),
                  "version_number": after.version_number},
        "summary": summary,
        "unnumbered": unnumbered,
        # Numbering is the document's own (34.12), so a comparison can only be as
        # complete as the numbering is. Stated rather than implied, because a
        # reader is entitled to know how much of the document this aligned.
        "matched_on": "section_number",
        "clauses": [{
            "status": c.status,
            "section_number": c.section_number,
            "section_title": c.section_title,
            "before": c.before,
            "after": c.after,
            "findings": c.findings,
        } for c in changes],
    }


def _section_sort_key(section: str) -> tuple:
    """Document order for clause numbers: 2 before 10, 2.2 before 2.10."""
    parts = re.split(r"[.\-]", section)
    key: list[tuple[int, Any]] = []
    for part in parts:
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part.lower()))
    return tuple(key)

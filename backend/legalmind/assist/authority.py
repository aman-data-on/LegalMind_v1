"""The source authority model — roadmap §1, `AM-79` (AB-29).

One vocabulary for every knowledge domain, derived from metadata each domain ALREADY
records (nothing new is inferred, nothing is guessed):

  COMPANY_CONSTITUTION       the ratified Legal Constitution, and standards drawn from it
  APPROVED_COMPANY_DOCUMENT  a ratified standard drawn from company paper (MSA template,
                             ToS, SLA, the reference NDA) — Constitution §7 level 3
  EXECUTED_DOCUMENT          an uploaded version declared FINAL_SIGNED
  DRAFT_DOCUMENT             an uploaded version declared COMPANY_DRAFT / CLIENT_MODIFIED
  HISTORICAL_EXCEPTION       past negotiated paper the Constitution records — never policy
  PRIMARY_LAW                a supplied statute, rule or direction
  SECONDARY_REFERENCE        commentary on the law, incl. the Constitution's own reading
  USER_MATERIAL              what the reader pasted or attached in this conversation —
                             never a company source (Ask plan 1.4, `AM-113`)

Authority is QUESTION-dependent (roadmap §1): these labels say what a source IS; which
one is primary for a given question is decided later, in the evidence layer. An
undeclared execution status is None — unknown is never reported as executed.
Status values (CURRENT · SUPERSEDED · HISTORICAL · UNRATIFIED · REPEALED) are the same
CHECK-constrained vocabulary the knowledge tables carry.
"""
from __future__ import annotations

AUTHORITIES = ("COMPANY_CONSTITUTION", "APPROVED_COMPANY_DOCUMENT", "EXECUTED_DOCUMENT",
               "DRAFT_DOCUMENT", "HISTORICAL_EXCEPTION", "PRIMARY_LAW",
               "SECONDARY_REFERENCE")
#: Not in AUTHORITIES, which mirrors the `knowledge_items` CHECK: user material is never
#: a knowledge record, only an evidence label in one conversation.
USER_MATERIAL = "USER_MATERIAL"


def of_standard(source_document: str | None) -> str:
    return ("COMPANY_CONSTITUTION" if "Legal Constitution" in (source_document or "")
            else "APPROVED_COMPANY_DOCUMENT")


def of_document(version_role: str | None) -> str | None:
    return {"FINAL_SIGNED": "EXECUTED_DOCUMENT", "COMPANY_DRAFT": "DRAFT_DOCUMENT",
            "CLIENT_MODIFIED": "DRAFT_DOCUMENT"}.get(version_role or "")


def of_statute(official_title: str) -> tuple[str, str]:
    """(authority, status). The repeal marker is the one `statutes` already filters on."""
    from legalmind.assist.statutes import _REPEALED_MARKER
    return "PRIMARY_LAW", "REPEALED" if _REPEALED_MARKER in official_title else "CURRENT"

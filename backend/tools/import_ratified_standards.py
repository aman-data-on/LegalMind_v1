"""Import the ratified Company Standards into the runtime database.

The files under ``backend/config/company_standards/`` are the owner's ratified
positions, complete with provenance. Until this tool existed they were read only
by the golden-corpus loader — the *tests* knew the standards, the *application*
did not. This closes that gap without inventing anything: every value written
comes from a ratified file, and the tool refuses files that lack a document type
or provenance.

Idempotent by content: a Requirement whose latest standard configuration already
equals the file's is skipped; a changed file appends a new version (locked rule
16 — never edits); an unknown code is created. Re-running against an unchanged
directory changes nothing and publishes nothing new (snapshot identity dedupes
by hash).

What this tool deliberately does NOT do:
* invent mapping or evaluation rules — a file must carry `mapping_rules` and
  `evaluation_rules` blocks, or its Requirement is imported as DRAFT-only and
  reported as unpublishable (35.9 fixes no threshold; assuming one here would
  put a number nobody chose into every Review);
* invent a Legal Rule — a `legal_rule` block is written only when the file
  carries one, and only the approved zero-tolerance rule is accepted (owner
  approval 2026-08-20): any tolerance band is refused, because the policy is
  that none exists;
* touch existing Reviews — publishing pins new snapshots only (rule 16).

Usage:
    python3 -m tools.import_ratified_standards [--publish] [--actor-email EMAIL]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from legalmind import config
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.domain.document_types import is_document_type
from legalmind.evaluation.corpus import RATIFIED_STANDARDS_DIR


class ImportRefused(Exception):
    """A file is not importable as ratified configuration."""


def _validate(path: Path, payload: dict) -> None:
    code = payload.get("requirement_code")
    if not code or path.stem != code:
        raise ImportRefused(
            f"{path.name}: requirement_code {code!r} must equal the filename")
    cfg = payload.get("configuration") or {}
    ev_type = payload.get("evaluator_type", "NUMERIC_COMPARISON")
    if ev_type not in ("NUMERIC_COMPARISON", "PRESENCE"):
        raise ImportRefused(
            f"{path.name}: evaluator_type {ev_type!r} is not a V1 evaluator")
    # A standard must state a position its evaluator can read: `preferred` for
    # numeric, `expected_presence` for presence. A file with neither would
    # import as a standard that evaluates nothing (ENG-09: refuse, not guess).
    if ev_type == "NUMERIC_COMPARISON" and cfg.get("preferred") is None:
        raise ImportRefused(f"{path.name}: numeric standard declares no `preferred`")
    if ev_type == "PRESENCE" and cfg.get("expected_presence") is None:
        raise ImportRefused(f"{path.name}: presence standard declares no `expected_presence`")
    if not is_document_type(cfg.get("document_type")):
        raise ImportRefused(
            f"{path.name}: configuration.document_type {cfg.get('document_type')!r} "
            "is not a locked Step 6 value")
    for field in ("ratified", "source_document", "source_clause"):
        if not payload.get(field):
            raise ImportRefused(
                f"{path.name}: missing {field} — a ratified standard without "
                "provenance is indistinguishable from an invented one (rule 21)")
    # Exactly one Legal Rule is approved (owner, 2026-08-20): the zero-tolerance
    # blanket. Anything else — a tolerance band in particular — is an acceptance
    # policy nobody approved, and importing it would put it into every Review.
    lr = payload.get("legal_rule")
    if lr is not None:
        approved = {"deviation_outcome": "UNACCEPTABLE",
                    "unlimited_outcome": "UNACCEPTABLE"}
        if (lr.get("configuration") or {}) != approved:
            raise ImportRefused(
                f"{path.name}: legal_rule.configuration is not the approved "
                f"zero-tolerance rule {approved}; no other Legal Rule is "
                "approved and none is invented here (rule 21)")
        if lr.get("rule_type") not in ("THRESHOLD", "ALLOWED_VALUES", "PRESENCE"):
            raise ImportRefused(
                f"{path.name}: legal_rule.rule_type {lr.get('rule_type')!r} is "
                "not a locked rule type")


def _resolve_actor(db: Session, email: str | None):
    stmt = select(M.User).order_by(M.User.created_at)
    if email:
        stmt = select(M.User).where(M.User.email == email)
    user = db.execute(stmt.limit(1)).scalars().first()
    if user is None:
        raise ImportRefused(
            f"no user found{f' for {email!r}' if email else ''}; configuration "
            "rows record created_by, and an import with no actor would be an "
            "unattributable configuration change")
    return user


def import_standards(db: Session, *, actor_email: str | None = None,
                     publish: bool = False) -> list[str]:
    report: list[str] = []
    actor = _resolve_actor(db, actor_email)
    files = sorted(RATIFIED_STANDARDS_DIR.glob("*.json"))
    if not files:
        raise ImportRefused(f"no ratified standards in {RATIFIED_STANDARDS_DIR}")

    publishable: list[str] = []
    for path in files:
        payload = json.loads(path.read_text())
        _validate(path, payload)
        code = payload["requirement_code"]
        cfg = payload["configuration"]
        mapping_rules = payload.get("mapping_rules")
        evaluation_rules = payload.get("evaluation_rules")
        legal_rule = payload.get("legal_rule")

        req = db.execute(
            select(M.Requirement).where(M.Requirement.code == code)
        ).scalars().first()
        if req is None:
            req = M.Requirement(code=code, status=E.ConfigStatus.DRAFT)
            db.add(req); db.flush()
            report.append(f"{code}: created")

        latest = db.execute(
            select(M.RequirementVersion)
            .where(M.RequirementVersion.requirement_id == req.id)
            .order_by(M.RequirementVersion.version_number.desc())
            .limit(1)).scalars().first()

        if latest is not None:
            current = db.execute(
                select(M.CompanyStandardVersion)
                .where(M.CompanyStandardVersion.requirement_version_id == latest.id)
                .order_by(M.CompanyStandardVersion.version_number.desc())
                .limit(1)).scalars().first()
            current_lr = db.execute(
                select(M.LegalRuleVersion)
                .where(M.LegalRuleVersion.requirement_version_id == latest.id)
                .order_by(M.LegalRuleVersion.version_number.desc())
                .limit(1)).scalars().first()
            # Idempotence covers the Legal Rule too: a file that gained (or
            # changed) its rule must append a new version, not be skipped.
            lr_unchanged = (
                (legal_rule is None and current_lr is None)
                or (legal_rule is not None and current_lr is not None
                    and current_lr.configuration == legal_rule["configuration"]))
            if (current is not None and current.configuration == cfg
                    and lr_unchanged):
                report.append(f"{code}: unchanged (version {latest.version_number})")
                if mapping_rules and evaluation_rules:
                    publishable.append(code)
                continue

        rv = M.RequirementVersion(
            requirement_id=req.id,
            version_number=(latest.version_number + 1) if latest else 1,
            name=payload.get("name") or code,
            description=f"Imported from ratified {path.name} "
                        f"(ratified {payload['ratified']}; "
                        f"source: {payload['source_document']}, "
                        f"{payload['source_clause']})",
            evaluator_type=E.EvaluatorType(
                payload.get("evaluator_type", "NUMERIC_COMPARISON")),
            created_by=actor.id)
        db.add(rv); db.flush()
        db.add(M.CompanyStandardVersion(
            requirement_version_id=rv.id, version_number=1,
            configuration=cfg, created_by=actor.id))
        if mapping_rules and evaluation_rules:
            db.add(M.MappingRuleVersion(
                requirement_version_id=rv.id, version_number=1,
                rules=mapping_rules, created_by=actor.id))
            db.add(M.EvaluationRuleVersion(
                requirement_version_id=rv.id, version_number=1,
                evaluator_type=E.EvaluatorType(
                    payload.get("evaluator_type", "NUMERIC_COMPARISON")),
                rules=evaluation_rules, created_by=actor.id))
            publishable.append(code)
        if legal_rule is not None:
            db.add(M.LegalRuleVersion(
                requirement_version_id=rv.id, version_number=1,
                rule_type=E.RuleType(legal_rule["rule_type"]),
                configuration=legal_rule["configuration"],
                created_by=actor.id))
            report.append(f"{code}: zero-tolerance Legal Rule written "
                          "(owner approval 2026-08-20)")
        else:
            report.append(
                f"{code}: NO mapping/evaluation rules in the file — imported as "
                "an unpublishable draft. Rules are configuration the owner "
                "supplies; none was invented (35.9, rule 21).")
        db.flush()
        report.append(f"{code}: version {rv.version_number} written "
                      f"({cfg['document_type']}, preferred={cfg.get('preferred')})")

    if publish:
        if not publishable:
            report.append("publish skipped: no importable Requirement carries "
                          "mapping and evaluation rules")
        else:
            report.append(f"publish requested for: {', '.join(publishable)} — "
                          "use POST /configuration/publish (audited) rather than "
                          "this tool; publishing is a Legal-permission action.")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actor-email", default=None)
    parser.add_argument("--publish", action="store_true",
                        help="report what a publish would cover (the publish "
                             "itself stays in the audited API)")
    args = parser.parse_args()

    engine = create_engine(config.database_url())
    with Session(engine) as db:
        try:
            lines = import_standards(db, actor_email=args.actor_email,
                                     publish=args.publish)
        except ImportRefused as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 1
        db.commit()
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

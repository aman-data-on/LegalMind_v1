"""The post-migration reproducibility gate — locked 55.4 r3 and 55.5.

Locked 55.4 r3 is explicit that this is a gate and not an assumption:

```text
3. Reproducibility must survive migration. After any migration, historical
   Reviews must still replay identically (ENG-11) — this is a release-gate
   test (54.3), not an assumption.
```

and locked 55.5 puts it in the release sequence, between "migration applied
forward-only" and "deploy API + workers together".

--------------------------------------------------------------------------
What it checks, and why in this form
--------------------------------------------------------------------------
Two properties, both stated by locked rules and neither requiring any interpretation
of what a persisted row "meant":

```text
(1) Historical legal records are NOT REWRITTEN by a migration.   55.4 r1
    The Findings and Evaluations written before the migration are read back
    afterwards and compared field by field.

(2) The same inputs still produce the same legal output.          55.4 r3
    The same Document Version and the same configuration snapshot are
    analysed again after the migration, and the resulting legal record must
    match the one captured before it — which is exactly what AUD-04 and
    Step 28 r15 make a Review reproducible from.
```

Property (2) deliberately re-runs the whole pipeline — mapping, extraction,
evaluation, roll-up, persistence — rather than re-evaluating from a reconstructed
`EvaluatorInput`. A reconstruction would have to *infer* the original facts from the
persisted representation, and an inference that is subtly wrong would report
reproducibility it had not actually verified. Re-analysing from the pinned snapshot
uses the locked reproducibility mechanism itself.

The migration exercised is the **latest** one (`downgrade -1` then `upgrade head`),
because that is the one a release actually applies. Locked 55.4 r2 makes migrations
over legal data forward-only and additive, so the records must survive the round trip;
if a migration is destructive, that is what this gate is for.

**Everything configured here is STRUCTURAL and carries no legal meaning** (rule 21).
No fixture conclusion is asserted — only that two runs agree with each other.

Run it against a THROWAWAY database:

    LEGALMIND_REPRO_DATABASE_URL=postgresql+psycopg2://legalmind:legalmind@127.0.0.1/legalmind_v1_repro \\
    python3 -m tools.verify_reproducibility
"""

from __future__ import annotations

import io
import json
import os
import sys
import uuid
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session as DBSession
from sqlalchemy.orm import sessionmaker

from legalmind.analysis.service import run_analysis
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.ingestion.service import ingest_document
from legalmind.ingestion.storage import LocalFilesystemStorage
from tools.e2e_bootstrap import STRUCTURAL_CONFIGURATION, STRUCTURAL_PARAGRAPHS

DOCX_MIME = ("application/vnd.openxmlformats-officedocument"
             ".wordprocessingml.document")


def repro_url() -> str:
    return os.environ.get(
        "LEGALMIND_REPRO_DATABASE_URL",
        "postgresql+psycopg2://legalmind:legalmind@127.0.0.1/legalmind_v1_repro")


# --------------------------------------------------------------------------
# Database lifecycle
# --------------------------------------------------------------------------
def _recreate(url: str) -> None:
    parts = urlsplit(url)
    database = parts.path.lstrip("/")
    server = urlunsplit(parts._replace(path="/postgres"))
    engine = create_engine(server, future=True, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{database}"'))
    engine.dispose()
    # Fresh database, no pgvector; the migration refuses to create it. Try here.
    from tools.pg_extensions import ensure_vector_extension
    ensure_vector_extension(url)


def _alembic(url: str):
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def _upgrade(url: str, revision: str = "head") -> None:
    from alembic import command

    command.upgrade(_alembic(url), revision)


def _downgrade(url: str, revision: str) -> None:
    from alembic import command

    command.downgrade(_alembic(url), revision)


def _current_head(url: str) -> str:
    from alembic.script import ScriptDirectory

    return ScriptDirectory.from_config(_alembic(url)).get_current_head()


# --------------------------------------------------------------------------
# The STRUCTURAL fixture, built through the real services
# --------------------------------------------------------------------------
def _docx() -> bytes:
    import docx

    document = docx.Document()
    for paragraph in STRUCTURAL_PARAGRAPHS:
        document.add_paragraph(paragraph)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


def _configuration(db: DBSession, owner_id) -> uuid.UUID:
    cfg = STRUCTURAL_CONFIGURATION
    requirement = M.Requirement(code=f"REPRO-{uuid.uuid4().hex[:6]}",
                                status=E.ConfigStatus.ACTIVE)
    db.add(requirement)
    db.flush()
    rv = M.RequirementVersion(
        requirement_id=requirement.id, version_number=1, name=str(cfg["name"]),
        evaluator_type=E.EvaluatorType.NUMERIC_COMPARISON, created_by=owner_id)
    db.add(rv)
    db.flush()
    cs = M.CompanyStandardVersion(requirement_version_id=rv.id, version_number=1,
                                  configuration=cfg["company_standard"],
                                  created_by=owner_id)
    mr = M.MappingRuleVersion(requirement_version_id=rv.id, version_number=1,
                              rules=cfg["mapping_rules"], created_by=owner_id)
    er = M.EvaluationRuleVersion(
        requirement_version_id=rv.id, version_number=1,
        evaluator_type=E.EvaluatorType.NUMERIC_COMPARISON,
        rules=cfg["evaluation_rules"], created_by=owner_id)
    lr = M.LegalRuleVersion(
        requirement_version_id=rv.id, version_number=1,
        rule_type=E.RuleType.THRESHOLD,
        configuration=cfg["legal_rule"]["configuration"], created_by=owner_id)
    db.add_all([cs, mr, er, lr])
    db.flush()
    snapshot = M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex,
                                       created_by=owner_id)
    db.add(snapshot)
    db.flush()
    db.add(M.ConfigurationSnapshotItem(
        snapshot_id=snapshot.id, requirement_version_id=rv.id,
        company_standard_version_id=cs.id, legal_rule_version_id=lr.id,
        mapping_rule_version_id=mr.id, evaluation_rule_version_id=er.id))
    db.flush()
    return snapshot.id


def _seed(db: DBSession, storage) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    owner = M.User(email=f"repro-{uuid.uuid4().hex[:8]}@example.test",
                   name="Repro", status=E.UserStatus.ACTIVE)
    db.add(owner)
    db.flush()
    snapshot_id = _configuration(db, owner.id)

    contract = M.Contract(owner_id=owner.id, name="Repro contract",
                          contract_type="MSA",   # declared type — Step 6 / Q9
                          status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    result = ingest_document(db, storage, contract_id=contract.id,
                             uploaded_by=owner.id, data=_docx(),
                             filename="repro.docx", declared_mime=DOCX_MIME)
    return owner.id, result.document_version.id, snapshot_id


def _analyse(db: DBSession, owner_id, document_version_id, snapshot_id) -> uuid.UUID:
    review = M.Review(
        contract_id=db.get(M.DocumentVersion, document_version_id).contract_id,
        document_version_id=document_version_id,
        configuration_snapshot_id=snapshot_id,
        status=E.ReviewStatus.DRAFT, created_by=owner_id)
    db.add(review)
    db.flush()
    run_analysis(db, review, actor_id=owner_id, request_id="repro")
    db.commit()
    return review.id


# --------------------------------------------------------------------------
# The legal record, as a comparable value
# --------------------------------------------------------------------------
def legal_record(db: DBSession, review_id: uuid.UUID) -> list[dict]:
    """Everything about a Review's legal output that must not vary.

    Deliberately excludes ids and timestamps — they are per-row and per-run by
    construction, and comparing them would only ever report "these are two different
    rows". What is compared is what the specification makes reproducible: the
    classification, the rule outcome, the scope, the evaluator version, the persisted
    facts and diagnostics, and the evidence count (rule 11 — evidence must survive).
    """
    findings = db.execute(
        select(M.Finding).where(M.Finding.review_id == review_id)
        .order_by(M.Finding.requirement_version_id)
    ).scalars().all()

    record: list[dict] = []
    for finding in findings:
        evaluations = db.execute(
            select(M.Evaluation).where(M.Evaluation.finding_id == finding.id)
            .order_by(M.Evaluation.scope_key, M.Evaluation.evaluation_kind)
        ).scalars().all()
        record.append({
            "requirement_code": db.execute(
                select(M.Requirement.code)
                .join(M.RequirementVersion,
                      M.RequirementVersion.requirement_id == M.Requirement.id)
                .where(M.RequirementVersion.id == finding.requirement_version_id)
            ).scalar_one(),
            "classification": finding.classification.value,
            "status": finding.status.value,
            "evaluations": [
                {
                    "scope_key": ev.scope_key,
                    "scope_label": ev.scope_label,
                    "evaluation_kind": ev.evaluation_kind.value,
                    "classification": ev.classification.value,
                    "rule_outcome": ev.rule_outcome.value,
                    "evaluator_type": ev.evaluator_type.value,
                    # 45B.10 / AM-19 — the version that produced the result.
                    "evaluator_version": ev.evaluator_version,
                    "expected_value": ev.expected_value,
                    "actual_value": ev.actual_value,
                    "operator": ev.operator,
                    "result": ev.result,
                    "evidence_count": db.execute(
                        select(M.EvaluationEvidence)
                        .where(M.EvaluationEvidence.evaluation_id == ev.id)
                    ).all().__len__(),
                }
                for ev in evaluations
            ],
        })
    return record


def digest(record: list[dict]) -> str:
    import hashlib

    return hashlib.sha256(
        json.dumps(record, sort_keys=True, default=str).encode()).hexdigest()


# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Post-migration reproducibility gate")
    parser.add_argument("--keep", action="store_true",
                        help="do not recreate the database first")
    args = parser.parse_args(argv)

    url = repro_url()
    print("Post-migration reproducibility gate — locked 55.4 r3, 55.5")
    print("STRUCTURAL fixture; no legal conclusion is asserted (rule 21).\n")

    if not args.keep:
        _recreate(url)
    _upgrade(url)
    head = _current_head(url)
    print(f"  migrated to head {head}")

    engine = create_engine(url, future=True)
    Session = sessionmaker(bind=engine, future=True)
    storage = LocalFilesystemStorage(os.path.abspath(".e2e/repro-objects"))

    with Session() as db:
        owner_id, document_version_id, snapshot_id = _seed(db, storage)
        db.commit()
        first_review = _analyse(db, owner_id, document_version_id, snapshot_id)
        before = legal_record(db, first_review)
    print(f"  analysed review {first_review}: "
          f"{len(before)} finding(s), digest {digest(before)[:16]}")

    # ---- the migration a release actually applies -------------------------
    revisions = _list_revisions(url)
    if len(revisions) < 2:                                  # pragma: no cover
        print("  only one migration exists; nothing to round-trip")
        previous = None
    else:
        previous = revisions[1]
        _downgrade(url, previous)
        _upgrade(url)
        print(f"  round-tripped the latest migration ({previous} -> {head})")

    failures: list[str] = []

    # ---- (1) historical records were not rewritten (55.4 r1) --------------
    with Session() as db:
        after = legal_record(db, first_review)
    if after != before:
        failures.append(
            "the migration CHANGED an existing legal record — 55.4 r1 forbids "
            "rewriting historical legal records")
    print(f"  historical record after migration: digest {digest(after)[:16]} "
          f"({'unchanged' if after == before else 'CHANGED'})")

    # ---- (2) the same inputs still produce the same output (55.4 r3) ------
    with Session() as db:
        second_review = _analyse(db, owner_id, document_version_id, snapshot_id)
        replayed = legal_record(db, second_review)
    same = replayed == before
    print(f"  re-analysed the same document + snapshot: digest "
          f"{digest(replayed)[:16]} ({'identical' if same else 'DIFFERENT'})")
    if not same:
        failures.append(
            "re-analysing the same Document Version against the same configuration "
            "snapshot produced a DIFFERENT legal record — ENG-11 / AUD-04 / 55.4 r3")

    engine.dispose()

    print()
    if failures:
        for failure in failures:
            print(f"  FAIL  {failure}")
        return 1
    print("  PASS  reproducibility survived the migration, and the historical "
          "record was not rewritten.")
    return 0


def _list_revisions(url: str) -> list[str]:
    """Revision ids, newest first."""
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(_alembic(url))
    return [revision.revision for revision in script.walk_revisions()]


if __name__ == "__main__":
    sys.exit(main())

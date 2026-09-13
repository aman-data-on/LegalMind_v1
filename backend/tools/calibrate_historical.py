"""Calibrate the published configuration against real signed counterparty paper.

The owner supplied a Drive folder of historical signed documents on 2026-09-14
"for historical calibration and testing only", with three standing conditions:

    * they are HISTORICAL EVIDENCE, never a company position (some terms have
      since changed);
    * they are always validated against the CURRENT Constitution;
    * no counterparty name and no clause text enters the repository (locked 54.6).

So this tool reads from ``LEGALMIND_SOURCE_MATERIAL_DIR/historical/`` — which is
gitignored — refers to every document by an anonymised handle derived from its
filename, and prints aggregate numbers only. Nothing it produces contains a
counterparty name or a quoted clause, which is what makes its output safe to
paste into a report or commit as a measurement.

    python3 -m tools.calibrate_historical [--json out.json] [--limit N]

What it measures, per document and in aggregate:

    applied / not applicable / same position   the AM-61 applicability record
    MATCH / DEVIATION / MISSING / CONFLICT     the classifications
    UNABLE_TO_EVALUATE                         "Needs a decision"
    findings with no evidence                  MISSING is the only legitimate one
    duplicate positions                        two findings, one Constitution position
    unmatched provisions                       clauses no finding cited (REC-02)
    model calls / wall clock                   the cost of the semantic stage

It asserts nothing. Calibration is a measurement, and locked 35.10 wants the
measurement recorded before a terminology set is trusted — not a pass/fail.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import uuid
from collections import Counter
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from legalmind.analysis.service import run_analysis
from legalmind.assist import generation
from legalmind.config import database_url, source_material_dir
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.ingestion.service import ingest_document
from legalmind.ingestion.storage import LocalFilesystemStorage
from legalmind.ingestion.validation import DOCX_MIME, PDF_MIME

#: Document-type handles, derived from the filename's own words. Never a
#: counterparty name — the handle is what appears in every line of output.
_KINDS = (
    ("partner", "PA"), ("channel", "PA"), ("distribution", "DIST"),
    ("vendor", "VEN"), ("anti-poaching", "ANTI"), ("nda", "NDA"),
    ("non-disclosure", "NDA"), ("non disclosure", "NDA"),
    ("sla", "SLA"), ("service level", "SLA"), ("msa", "MSA"),
    ("master service", "MSA"), ("purchase order", "PO"), ("order form", "PO"),
    ("amendment", "AMD"), ("addendum", "AMD"),
)

MIMES = {".pdf": PDF_MIME, ".docx": DOCX_MIME}


def handle(path: Path, seen: Counter) -> str:
    """`HIST-PA-01` — kind plus a counter, never the counterparty."""
    lowered = path.name.lower()
    kind = next((code for word, code in _KINDS if word in lowered), "DOC")
    seen[kind] += 1
    return f"HIST-{kind}-{seen[kind]:02d}"


def _duplicate_positions(db: Session, review_id: uuid.UUID) -> int:
    """Findings that measure a Constitution position another finding already
    measured — the duplicate-finding rate AM-61 r3 exists to drive to zero."""
    rows = db.execute(
        select(M.Requirement.code, M.CompanyStandardVersion.configuration)
        .join(M.RequirementVersion, M.RequirementVersion.requirement_id == M.Requirement.id)
        .join(M.Finding, M.Finding.requirement_version_id == M.RequirementVersion.id)
        .join(M.ConfigurationSnapshotItem,
              M.ConfigurationSnapshotItem.requirement_version_id == M.RequirementVersion.id)
        .join(M.CompanyStandardVersion,
              M.CompanyStandardVersion.id
              == M.ConfigurationSnapshotItem.company_standard_version_id)
        .where(M.Finding.review_id == review_id)
    ).all()
    positions = Counter()
    for _code, cfg in rows:
        cfg = cfg or {}
        section = (cfg.get("constitution") or {}).get("section")
        if section is None:
            continue
        if "preferred" in cfg:
            key = (section, cfg.get("preferred"), cfg.get("unit"),
                   cfg.get("basis"), cfg.get("scope_key"))
        else:
            key = (section, cfg.get("expected_presence"), cfg.get("scope_key"))
        positions[key] += 1
    return sum(n - 1 for n in positions.values() if n > 1)


def calibrate(db: Session, storage, path: Path, name: str, snapshot_id: uuid.UUID) -> dict:
    calls = {"n": 0}
    real = generation.generate_raw

    def counting(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    generation.generate_raw = counting
    started = time.monotonic()
    try:
        contract = M.Contract(owner_id=_owner(db).id, name=name,
                              contract_type=None,        # AM-64: never declared
                              status=E.ContractStatus.ACTIVE)
        db.add(contract); db.flush()
        result = ingest_document(db, storage, contract_id=contract.id,
                                 uploaded_by=contract.owner_id,
                                 data=path.read_bytes(), filename=path.name,
                                 declared_mime=MIMES[path.suffix.lower()])
        review = M.Review(contract_id=contract.id,
                          document_version_id=result.document_version.id,
                          configuration_snapshot_id=snapshot_id,
                          status=E.ReviewStatus.DRAFT, created_by=contract.owner_id)
        db.add(review); db.flush()
        run = run_analysis(db, review)
    finally:
        generation.generate_raw = real

    classifications = Counter(o.classification for o in run.outcomes if o.classification)
    applicability = Counter(c["outcome"] for c in run.applicability)
    evidence_free = sum(
        1 for o in run.outcomes
        if o.finding_id and o.classification != "MISSING"
        and not db.execute(select(M.FindingEvidence)
                           .where(M.FindingEvidence.finding_id == o.finding_id)).first())
    return {
        "document": name,
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()[:16],
        "clauses": db.execute(
            select(M.DocumentEvidence)
            .where(M.DocumentEvidence.document_version_id == result.document_version.id)
        ).scalars().all().__len__(),
        "status": run.review_status,
        "failures": [o.failure for o in run.outcomes if o.failure][:3],
        "requirements_in_snapshot": run.requirements_in_snapshot,
        "applicability": dict(applicability),
        "classifications": dict(classifications),
        "findings": run.findings_created,
        # A finding other than MISSING with no evidence is a defect: rule 11
        # requires every finding to trace to the text it rests on.
        "findings_without_evidence": evidence_free,
        "duplicate_positions": _duplicate_positions(db, review.id),
        "unmatched_provisions": run.unmatched_provisions,
        "model_calls": calls["n"],
        "seconds": round(time.monotonic() - started, 1),
    }


def _owner(db: Session):
    owner = db.execute(select(M.User).order_by(M.User.created_at)).scalars().first()
    if owner is None:
        raise SystemExit("no user in the database to own the calibration contracts")
    return owner


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dir", default=None,
                    help="default: LEGALMIND_SOURCE_MATERIAL_DIR/historical")
    args = ap.parse_args(argv)

    root = Path(args.dir or (Path(source_material_dir()) / "historical"))
    if not root.is_dir():
        print(f"SKIP  no historical corpus at {root}")
        print("      The owner's Drive folder holds the signed documents; place the")
        print("      PDFs and DOCXs there (the directory is gitignored) and re-run.")
        return 0
    files = sorted(p for p in root.iterdir() if p.suffix.lower() in MIMES)
    if not files:
        print(f"SKIP  {root} holds no .pdf or .docx")
        return 0
    files = files[: args.limit] if args.limit else files

    engine = create_engine(database_url())
    rows: list[dict] = []
    with engine.connect() as conn:
        outer = conn.begin()
        db = Session(bind=conn, join_transaction_mode="create_savepoint")
        try:
            snapshot = db.execute(
                select(M.ConfigurationSnapshot)
                .order_by(M.ConfigurationSnapshot.created_at.desc())).scalars().first()
            if snapshot is None:
                raise SystemExit("no published configuration snapshot to calibrate against")
            storage = LocalFilesystemStorage(root / ".objects")
            seen: Counter = Counter()
            for path in files:
                name = handle(path, seen)
                try:
                    rows.append(calibrate(db, storage, path, name, snapshot.id))
                except Exception as exc:
                    rows.append({"document": name, "error": f"{type(exc).__name__}: {exc}"})
                print(f"  {rows[-1].get('document')}: "
                      + json.dumps({k: v for k, v in rows[-1].items()
                                    if k not in ("document", "sha256")}))
        finally:
            db.close()
            # Calibration never writes: everything above is rolled back.
            outer.rollback()

    ok = [r for r in rows if "error" not in r]
    total = Counter()
    for r in ok:
        total.update(r["classifications"])
        total.update({f"applicability.{k}": v for k, v in r["applicability"].items()})
        for key in ("findings", "findings_without_evidence", "duplicate_positions",
                    "unmatched_provisions", "model_calls", "clauses"):
            total[key] += r[key]
    print("\n=== aggregate over", len(ok), "document(s) ===")
    for key in sorted(total):
        print(f"  {key:34} {total[key]}")
    if args.json:
        Path(args.json).write_text(json.dumps({"documents": rows, "aggregate": dict(total)},
                                              indent=1))
        print("wrote", args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

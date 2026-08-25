"""Retrieval benchmark — `AM-26` r2's "selected by measurement", made runnable.

    python3 -m tools.benchmark_retrieval [--limit-docs N] [--json PATH]

`AM-26` r2: *"Selection proceeds from the smallest candidate upward and stops at the
first that meets the quality bar. A larger model is not adopted for headroom."* That is
a comparison, and a comparison needs a fixed measuring instrument that exists before any
candidate does. This is that instrument.

--------------------------------------------------------------------------
Where the probes come from, and why none of them is authored
--------------------------------------------------------------------------
Rule 21 and `AM-31` m5 govern evaluation material. The distinction that matters here:

    a RETRIEVAL label says   "the text about X is in §17.2"
                             — a locatable fact about a document, mechanically
                               checkable by reading it, asserting no legal position

    an ANSWER label says     "our liability cap is 12 months"
                             — a legal position, and it must be SUPPLIED (AM-31 m5)

A3 measures retrieval, so this harness derives every probe **mechanically from the real
supplied documents** and authors none. Three probe families come out of that honestly:

    section_number      the document states "17.2"; the query is "17.2" and the answer
                        is the chunk that opens with it. Zero judgment.
    exact_terminology   an n-gram occurring in exactly ONE chunk of the document; the
                        query is that n-gram and the answer is that chunk. Uniqueness is
                        computed, not chosen.
    unanswerable        an n-gram taken from a DIFFERENT document and verified absent
                        from this one; the correct result is empty. `AM-28` requires
                        unanswerable questions and calls correct refusal half the bar.

Two families genuinely cannot be derived this way, and are reported as gaps rather than
faked: **paraphrase/semantic similarity** and **legal phrasing**, both of which need a
human-written question whose wording deliberately differs from the document's. Those
need supplied material. Inventing them here would be exactly the "do not invent
evaluation results" failure — and worse, they are the categories an embedding model is
supposed to win, so faking them would bias the selection toward the conclusion.

--------------------------------------------------------------------------
No document text enters the repository
--------------------------------------------------------------------------
Locked 54.6. Probes are generated at run time from `LEGALMIND_SOURCE_MATERIAL_DIR`
(gitignored) and never written to a fixture. The report prints counts, scores and
section numbers — never clause text. Absence of the source material is a SKIP, not a
failure, which is the same posture `test_source_material.py` already takes: CI has no
documents, and "cannot measure here" is not "measured and fine".
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from legalmind import config
from legalmind.assist.chunking import leading_section_ref
from legalmind.assist.embedding import LexicalStrategy, RetrievalStrategy
from legalmind.assist.indexing import index_document_version
from legalmind.assist.onnx_backend import OnnxEmbeddingBackend, model_root
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.ingestion.service import ingest_document
from legalmind.ingestion.storage import LocalFilesystemStorage

# Probes per family per document. Bounded so a run stays quick enough to be used while
# iterating; raise it for a decision-grade run and say which number was used.
PROBES_PER_FAMILY = 12
NGRAM_WORDS = 4
TOP_K = 10

# Words too common to make a distinctive probe. Not a linguistic stopword list — these
# are the terms that appear in every clause of every contract, so an n-gram built from
# them alone tests nothing.
_BORING = {
    "the", "and", "of", "to", "in", "any", "or", "for", "shall", "be", "this",
    "agreement", "party", "parties", "customer", "provider", "such", "under",
    "with", "by", "as", "that", "which", "may", "not", "is", "are", "will",
}


@dataclass
class Probe:
    family: str
    query: str
    expected_chunk_ids: set = field(default_factory=set)
    document: str = ""


@dataclass
class FamilyResult:
    family: str
    probes: int = 0
    hit_at_1: int = 0
    hit_at_k: int = 0
    reciprocal_rank_sum: float = 0.0
    correct_refusals: int = 0
    wrongly_answered: int = 0

    def as_row(self) -> dict:
        n = self.probes or 1
        return {
            "family": self.family,
            "probes": self.probes,
            "precision@1": round(self.hit_at_1 / n, 3),
            f"recall@{TOP_K}": round(self.hit_at_k / n, 3),
            "mrr": round(self.reciprocal_rank_sum / n, 3),
            "correct_refusals": self.correct_refusals,
            "wrongly_answered": self.wrongly_answered,
        }


# --------------------------------------------------------------------------
# Corpus setup
# --------------------------------------------------------------------------
def _pdf_bytes(path: pathlib.Path) -> bytes:
    return path.read_bytes()


def _ingest_corpus(db, storage, documents: list[pathlib.Path]) -> dict[str, uuid.UUID]:
    """Ingest each document through the REAL pipeline and index it.

    Through `ingest_document` rather than by calling the parser directly, so the
    benchmark measures the chunks the application would actually build.
    """
    owner = M.User(email=f"bench-{uuid.uuid4().hex[:8]}@example.test",
                   name="benchmark", status=E.UserStatus.ACTIVE)
    db.add(owner)
    db.flush()

    versions: dict[str, uuid.UUID] = {}
    for path in documents:
        contract = M.Contract(owner_id=owner.id, name=path.stem,
                              contract_type="MSA", status=E.ContractStatus.ACTIVE)
        db.add(contract)
        db.flush()
        try:
            result = ingest_document(
                db, storage, contract_id=contract.id, uploaded_by=owner.id,
                data=_pdf_bytes(path), filename=path.name,
                declared_mime="application/pdf")
        except Exception as exc:
            print(f"  {path.name}: NOT INGESTED ({type(exc).__name__})")
            continue
        outcome = index_document_version(db, result.document_version.id)
        versions[path.name] = result.document_version.id
        print(f"  {path.name:28s} evidence={result.evidence_count:4d} "
              f"chunks={outcome.chunks_written:4d}")
    db.flush()
    return versions


def _chunks(db, document_version_id) -> list[tuple[uuid.UUID, str]]:
    schema = config.assist_schema()
    return [(r[0], r[1]) for r in db.execute(text(
        f'SELECT id, content FROM "{schema}".chunks '
        'WHERE document_version_id = :dv ORDER BY ordinal'),
        {"dv": document_version_id}).all()]


# --------------------------------------------------------------------------
# Probe derivation — mechanical, no authored queries
# --------------------------------------------------------------------------
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]+")


def _ngrams(content: str, n: int = NGRAM_WORDS) -> set[str]:
    words = [w.lower() for w in _WORD.findall(content)]
    out = set()
    for i in range(len(words) - n + 1):
        window = words[i:i + n]
        # Reject a window that is entirely boilerplate: it would appear everywhere and
        # measure nothing.
        if all(w in _BORING for w in window):
            continue
        out.add(" ".join(window))
    return out


def _derive_probes(chunks: list[tuple[uuid.UUID, str]], document: str,
                   foreign_ngrams: set[str]) -> list[Probe]:
    probes: list[Probe] = []

    # --- section_number: the document states it, so the query is it -----------
    by_section: dict[str, set] = defaultdict(set)
    for cid, content in chunks:
        ref = leading_section_ref(content)
        if ref:
            by_section[ref].add(cid)
    # Only sections that identify exactly one chunk: a number appearing twice has no
    # single right answer, and scoring it either way would be arbitrary.
    unique_sections = [(s, ids) for s, ids in sorted(by_section.items())
                       if len(ids) == 1 and "." in s]
    for section, ids in unique_sections[:PROBES_PER_FAMILY]:
        probes.append(Probe("section_number", section, set(ids), document))

    # --- exact_terminology: an n-gram unique to one chunk ---------------------
    counts: Counter = Counter()
    owner_of: dict[str, uuid.UUID] = {}
    for cid, content in chunks:
        for gram in _ngrams(content):
            counts[gram] += 1
            owner_of.setdefault(gram, cid)
    unique = [g for g, c in counts.items() if c == 1]
    # Sorted for reproducibility: no clock, no randomness, so two runs over the same
    # corpus produce the same probe set and the numbers are comparable.
    for gram in sorted(unique)[:PROBES_PER_FAMILY]:
        probes.append(Probe("exact_terminology", gram, {owner_of[gram]}, document))

    # --- unanswerable: verified absent from THIS document ---------------------
    #
    # A first version required only that the 4-gram be absent, and that turned out to
    # be too weak a claim: `websearch_to_tsquery` ANDs the stemmed terms, so a chunk
    # containing all four words *scattered* matches, and topically it may well be a
    # reasonable result. Scoring that as "wrongly answered" measured the probe design
    # rather than the engine.
    #
    # So a probe now also requires at least one constituent word to be absent from the
    # document's entire vocabulary. A match is then unambiguously spurious: the engine
    # returned something for a query containing a word the document never uses.
    local = set(counts)
    vocabulary = {w for _, content in chunks for w in
                  (x.lower() for x in _WORD.findall(content))}
    candidates = []
    for gram in sorted(foreign_ngrams - local):
        if any(word not in vocabulary for word in gram.split()):
            candidates.append(gram)
    for gram in candidates[:PROBES_PER_FAMILY]:
        probes.append(Probe("unanswerable", gram, set(), document))

    return probes


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------
def _score(strategy: RetrievalStrategy, db, versions: dict[str, uuid.UUID],
           probes: list[Probe]) -> dict[str, FamilyResult]:
    results: dict[str, FamilyResult] = defaultdict(lambda: FamilyResult(""))
    for probe in probes:
        fam = results.setdefault(probe.family, FamilyResult(probe.family))
        fam.family = probe.family
        fam.probes += 1
        ranked = strategy.rank(db, document_version_id=versions[probe.document],
                               query=probe.query, limit=TOP_K)
        ids = [cid for cid, _ in ranked]

        if not probe.expected_chunk_ids:
            # Unanswerable. Returning nothing is correct; returning anything is a
            # wrong answer, and `AM-28` weighs that in both directions.
            if ids:
                fam.wrongly_answered += 1
            else:
                fam.correct_refusals += 1
            continue

        rank = next((i for i, cid in enumerate(ids, start=1)
                     if cid in probe.expected_chunk_ids), None)
        if rank is not None:
            fam.hit_at_k += 1
            fam.reciprocal_rank_sum += 1.0 / rank
            if rank == 1:
                fam.hit_at_1 += 1
    return results


def _print_table(label: str, results: dict[str, FamilyResult]) -> None:
    print(f"\n  strategy: {label}")
    print(f"    {'family':20s} {'probes':>6s} {'P@1':>6s} {'R@' + str(TOP_K):>6s} "
          f"{'MRR':>6s} {'refused':>8s} {'wrong':>6s}")
    print("    " + "-" * 62)
    for fam in sorted(results):
        r = results[fam].as_row()
        print(f"    {r['family']:20s} {r['probes']:6d} {r['precision@1']:6.3f} "
              f"{r[f'recall@{TOP_K}']:6.3f} {r['mrr']:6.3f} "
              f"{r['correct_refusals']:8d} {r['wrongly_answered']:6d}")



# --------------------------------------------------------------------------
# Measurement-only strategies
# --------------------------------------------------------------------------
# These live in the harness, not in `legalmind/assist/`, deliberately. They embed a
# document's chunks in memory to compare candidates; the production path will rank in
# SQL so that `AM-25` r6's authorization sits inside the query. Shipping an in-memory
# ranker as product code would invite exactly the post-filter r7 forbids, so it is not
# shipped at all — it exists here to answer "which model", and nothing else.
#
# The scope is still applied before ranking: chunks are fetched for one authorized
# document version and nothing else is ever a candidate.
class VectorStrategy:
    """Dense retrieval with one candidate embedding model."""

    def __init__(self, backend, chunk_cache: dict):
        self._backend = backend
        self._cache = chunk_cache
        self.label = f"vector [{backend.identity} d={backend.dimensions}]"

    def rank(self, db, *, document_version_id, query: str, limit: int):
        ids, vectors = self._cache[document_version_id]
        if not ids:
            return []
        q = self._backend.embed([query])[0]
        scored = [(cid, sum(a * b for a, b in zip(vec, q, strict=True)))
                  for cid, vec in zip(ids, vectors, strict=True)]
        scored.sort(key=lambda t: t[1], reverse=True)
        return scored[:limit]


class HybridStrategy:
    """Reciprocal rank fusion of the lexical and dense rankings.

    RRF with k=60, the constant from the original formulation — a convention, not a
    tuned value, and recorded as such so nobody reads it as a measured optimum. Fusion
    weighting is exactly the kind of parameter that needs the evaluation set before it
    means anything.
    """

    K = 60

    def __init__(self, backend, chunk_cache: dict):
        self._lexical = LexicalStrategy()
        self._vector = VectorStrategy(backend, chunk_cache)
        self.label = f"hybrid RRF [{backend.identity}]"

    def rank(self, db, *, document_version_id, query: str, limit: int):
        fused: dict = defaultdict(float)
        for strategy in (self._lexical, self._vector):
            ranked = strategy.rank(db, document_version_id=document_version_id,
                                   query=query, limit=limit * 2)
            for position, (cid, _) in enumerate(ranked, start=1):
                fused[cid] += 1.0 / (self.K + position)
        return sorted(fused.items(), key=lambda t: t[1], reverse=True)[:limit]


def _embed_corpus(backend, all_chunks: dict, versions: dict) -> dict:
    """Embed every chunk once per candidate, so ranking cost is not measured as model cost."""
    cache: dict = {}
    for name, chunks in all_chunks.items():
        ids = [cid for cid, _ in chunks]
        texts = [content for _, content in chunks]
        vectors = backend.embed(texts) if texts else []
        cache[versions[name]] = (ids, vectors)
    return cache


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
def _bench_url() -> str:
    return os.environ.get(
        "LEGALMIND_BENCH_DATABASE_URL",
        "postgresql+psycopg2://legalmind:legalmind@127.0.0.1/legalmind_v1_bench")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-docs", type=int, default=6)
    ap.add_argument("--json", default=None)
    ap.add_argument("--candidates", default="",
                    help="comma-separated provisioned model repos to measure")
    args = ap.parse_args()

    source = pathlib.Path(config.source_material_dir())
    if not source.exists():
        print("SKIP  no source material at LEGALMIND_SOURCE_MATERIAL_DIR.")
        print("      Locked 54.6 keeps documents out of the repository, so this")
        print("      harness cannot run in CI. 'Cannot measure here' is not 'fine'.")
        return 0

    documents = sorted(p for p in source.glob("*.pdf"))[:args.limit_docs]
    if not documents:
        print("SKIP  no PDFs in the source material directory.")
        return 0

    print("Retrieval benchmark — AM-26 r2, selection by measurement")
    print("No document text enters the repository (54.6); probes are derived at run "
          "time.\n")

    # A throwaway database, recreated per run, so a measurement never depends on
    # residue from an earlier one.
    admin = create_engine(
        _bench_url().rsplit("/", 1)[0] + "/postgres",
        isolation_level="AUTOCOMMIT", future=True)
    name = _bench_url().rsplit("/", 1)[-1]
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        c.execute(text(f'CREATE DATABASE "{name}"'))
    admin.dispose()

    from alembic.config import Config

    from alembic import command
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", _bench_url())
    os.environ.setdefault("LEGALMIND_ASSIST_SCHEMA", "assist")
    command.upgrade(cfg, "head")

    engine = create_engine(_bench_url(), future=True)
    db = sessionmaker(bind=engine, future=True)()
    storage = LocalFilesystemStorage(".e2e/bench-objects")

    print("Ingesting and indexing:")
    versions = _ingest_corpus(db, storage, documents)
    if not versions:
        print("\nno document could be ingested; nothing to measure")
        return 1

    # Foreign n-grams for the unanswerable family: taken from other documents in the
    # set, then verified absent from the document under test.
    all_chunks = {name_: _chunks(db, dv) for name_, dv in versions.items()}
    all_ngrams = {name_: set().union(*(_ngrams(c) for _, c in chunks)) if chunks else set()
                  for name_, chunks in all_chunks.items()}

    probes: list[Probe] = []
    print("\nProbes derived (mechanically, none authored):")
    for name_, chunks in all_chunks.items():
        foreign: set[str] = set()
        for other, grams in all_ngrams.items():
            if other != name_:
                foreign |= grams
        derived = _derive_probes(chunks, name_, foreign)
        probes.extend(derived)
        per = Counter(p.family for p in derived)
        print(f"  {name_:28s} " + "  ".join(f"{k}={v}" for k, v in sorted(per.items())))

    strategies: list[RetrievalStrategy] = [LexicalStrategy()]

    # Candidate models, smallest first — `AM-26` r2: "Selection proceeds from the
    # smallest candidate upward and stops at the first that meets the quality bar."
    # Only models already provisioned locally are measured; `AM-26` r5 forbids fetching
    # weights at runtime, so an unprovisioned candidate is skipped and said so.
    for repo in [c.strip() for c in (args.candidates or "").split(",") if c.strip()]:
        directory = model_root() / repo.replace("/", "__") / "main"
        if not (directory / "manifest.json").exists():
            print(f"  candidate {repo}: NOT PROVISIONED (run provision() first) — skipped")
            continue
        backend = OnnxEmbeddingBackend(directory)
        cache = _embed_corpus(backend, all_chunks, versions)
        strategies.append(VectorStrategy(backend, cache))
        strategies.append(HybridStrategy(backend, cache))

    report: dict = {"probes": len(probes), "top_k": TOP_K, "strategies": {}}
    for strategy in strategies:
        results = _score(strategy, db, versions, probes)
        _print_table(strategy.label, results)
        report["strategies"][strategy.label] = {
            f: r.as_row() for f, r in results.items()}

    print("\n  NOT MEASURED — these need supplied material, and are not invented here:")
    print("    semantic_similarity   a question whose wording differs from the")
    print("                          document's; cannot be derived from the document")
    print("    legal_phrasing        the same, for domain-specific rewording")
    print("    Both are the categories an embedding model is meant to win, so faking")
    print("    them would bias the selection toward its own conclusion.")

    db.rollback()
    db.close()
    engine.dispose()

    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(report, indent=2))
        print(f"\n  wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

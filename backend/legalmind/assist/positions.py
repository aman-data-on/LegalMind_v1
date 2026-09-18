"""Domain A — position chunks over the ratified Company Standards (`AM-32` r3–r5).

Three properties of this module are locked consequences, not preferences:

**The ratified standard is the single source of truth** (r3). There is no positions
content table; a chunk's `content` is composed exclusively of the ratified file's own
verbatim fields, and the row FK-references the *published* `company_standard_versions`
row it derives from. Re-chunking a standard first hard-deletes the chunks of every
version of that standard (the `AM-27` r5 principle applied to configuration), so a
superseded version's text can never keep answering.

**Domain A output is extractive-only** (r4). Nothing in this module builds a
generation payload, and `service.py` must never pass a position chunk to
`generation.generate` — `AM-30` t3 forbids any Company Standard value in an egressing
payload. `tests/test_positions.py` pins the import boundary: this module imports no
generation code.

**Access is `assist.ask` AND `configuration.view`, inside the query** (r5). The
search function takes the caller's resolved permission set and returns nothing —
indistinguishable from an empty corpus — without both. There is no separate
"forbidden" outcome (`AM-25` r6/r7).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session as DBSession

from legalmind import config
from legalmind.db import models as M
from legalmind.domain.document_types import DOCUMENT_TYPES
from legalmind.domain.document_types import readable as readable_document_type
from legalmind.observability.logs import log_event
from legalmind.security import permissions as P

CHUNKING_ALGORITHM_VERSION = "positions-verbatim-2"

RATIFIED_STANDARDS_DIR = (
    Path(__file__).resolve().parents[2] / "config" / "company_standards")


class PositionChunkingRefused(Exception):
    """Raised when a ratified file cannot be chunked without inventing something."""


@dataclass(frozen=True)
class PositionHit:
    position_chunk_id: UUID
    standard_code: str
    document_type: str
    source_clause: str | None
    content: str
    score: float
    # `AM-32` r4 names a Domain A citation as "standard code, VERSION, source clause".
    # The code carried the first and third and silently dropped the second, so a reader
    # could not tell which version of a position they were being shown, nor whether it
    # was still current. Joined from company_standard_versions / requirements rather
    # than duplicated onto the chunk — the ratified standard stays the single source of
    # truth (r3). Optional so an un-joined hit (tests, older callers) stays constructible.
    standard_version: int | None = None
    ratification_status: str | None = None


# THE KIND OF PAPER THE READER NAMED — AND WHETHER WE HOLD A POSITION ON IT.
#
# A question that names a kind of paper is answerable only from positions about THAT
# paper. Until 2026-09-18 nothing compared the two, so "what is written about partner
# agreement in the constitution" returned three MSA standards under the sentence "The
# organization's approved position relevant to this question is quoted below" — a
# position the organization holds for a different document type, presented as though it
# answered the question. Zero Partner Agreement standards are ratified, or even
# proposed, so there was no right answer to rank higher: this is a fail-open of rule 15
# and of `AM-25` r4 (never state a position absent from a ratified Company Standard),
# not a ranking defect. No reranker fixes it, because an MSA clause does not become a
# Partner Agreement position by being scored better.
#
# EVERY PHRASE HERE RESOLVES TO A REAL `document_types.DOCUMENT_TYPES` MEMBER, which is
# what lets a named type actually be held, retrieved and cited. That was not true when
# this list was first written: the §31 types sat outside locked Step 6, and were
# recognised ONLY so the refusal could be honest. The owner resolved C-23 on 2026-09-18
# — Constitution-final text is ratified — and Step 6 now carries PARTNER_AGREEMENT,
# VENDOR_AGREEMENT and DISTRIBUTION_AGREEMENT, so those questions answer rather than
# refuse. The refusal path is unchanged and still correct for a type with no positions.
#
# Purchase Order maps to ORDER_FORM rather than to a type of its own: that is how this
# repository already models §31.11 (both its standards are typed ORDER_FORM and coded
# `PO-*`), and a separate type would have split one concept across two buckets.
_TYPE_PHRASES: tuple[tuple[str, str], ...] = (
    ("master services agreement", "MSA"), ("master service agreement", "MSA"),
    ("msa", "MSA"),
    ("non-disclosure agreement", "NDA"), ("nondisclosure agreement", "NDA"),
    ("confidentiality agreement", "NDA"), ("nda", "NDA"),
    ("terms of service", "TOS"), ("tos", "TOS"),
    ("service level agreement", "SLA"), ("sla", "SLA"),
    ("data processing agreement", "DPA"), ("dpa", "DPA"),
    ("acceptable use policy", "AUP"), ("aup", "AUP"),
    ("privacy policy", "PRIVACY_POLICY"),
    ("order form", "ORDER_FORM"),
    ("purchase order", "ORDER_FORM"), ("po", "ORDER_FORM"),   # §31.11's own two names
    ("amendment", "AMENDMENT"), ("addendum", "AMENDMENT"),
    # Legal Constitution L1.10 §31's own type names. See the note above.
    ("channel partner agreement", "PARTNER_AGREEMENT"),
    ("partner agreement", "PARTNER_AGREEMENT"),
    ("reseller agreement", "PARTNER_AGREEMENT"),     # §31.4 "Partner / Reseller"
    # The bare subject too: Constitution §31 defines "Partner" as a party to exactly
    # one kind of paper, and "what does our constitution say about partners" is the
    # live phrasing (2026-09-18). A question that ALSO names another type resolves to
    # two and so narrows nothing — see the docstring.
    ("partners", "PARTNER_AGREEMENT"), ("partner", "PARTNER_AGREEMENT"),
    ("vendor agreement", "VENDOR_AGREEMENT"),
    ("distribution agreement", "DISTRIBUTION_AGREEMENT"),
    ("distributor agreement", "DISTRIBUTION_AGREEMENT"),
)
_TYPE_BY_PHRASE = dict(_TYPE_PHRASES)
# Bounded by `\b` so the acronyms match words, not substrings. Alternation order is
# irrelevant: where one phrase contains another ("channel partner agreement" contains
# "partner agreement") both map to the same type, so the resolved SET is identical.
_TYPE_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(p) for p, _ in _TYPE_PHRASES) + r")\b", re.IGNORECASE)


def named_document_type(question: str) -> str | None:
    """The single document type this question names, or None.

    None when the question names none — the overwhelmingly common case, which keeps
    every existing question on its existing path — and also when it names more than
    one ("does our MSA say the same as the order form?"). Two named types is not a
    narrowing this function is entitled to pick between, so it declines to narrow.
    """
    found = {_TYPE_BY_PHRASE[m.group(1).lower()]
             for m in _TYPE_PATTERN.finditer(question or "")}
    return found.pop() if len(found) == 1 else None


def coverage(db: DBSession) -> tuple[str, ...]:
    """The document types the currently-active ratified corpus holds a position for.

    The Domain A analogue of `statutes.holdings`, and public in exactly the same way
    (`AM-46` r3): it names which KINDS of paper the organization has approved standards
    for, never what any of those standards says. Carries the `AM-71` exclusion, so a
    type whose only standards are retired is not advertised as covered.
    """
    schema = config.assist_schema()
    return tuple(r[0] for r in db.execute(sql_text(f"""
        SELECT DISTINCT pc.document_type
          FROM "{schema}".position_chunks pc
          JOIN company_standard_versions csv ON csv.id = pc.standard_version_id
          JOIN requirement_versions rv ON rv.id = csv.requirement_version_id
          JOIN requirements r ON r.id = rv.requirement_id
         WHERE r.status <> 'DEPRECATED'
         ORDER BY pc.document_type""")).all())


# A `source_document` names the paper a position came from, and 34 of the 40 ratified
# files append an INTERNAL locator to that name — a repo path, the
# `LEGALMIND_SOURCE_MATERIAL_DIR` env var, or a reviewer's note. Composed into the chunk
# it reached the reader verbatim (`AskDock` renders `position.content` in a blockquote),
# so "what is our liability cap?" answered with
# "docs/02-legal-domain/LEGAL_CONSTITUTION_L1.5.md; owner ruling 2026-09-08". Measured
# live 2026-09-15. It is also INDEXED, so `docs`, `pdf` and `md` are matchable lexemes.
#
# The locator is provenance metadata, never ratified legal text — it is not part of
# `source_quote`, so removing it changes no legal position and leaves `AM-32` r4's
# verbatim requirement untouched. The ratified files are NOT edited: they are
# configuration, and this is a display concern.
# The four locator shapes, kept general rather than enumerating the six strings the
# current corpus happens to use — a seventh ratified file must not reopen the leak.
# A first draft matched only `/`, `.md`, `.pdf` and `LEGALMIND_*`; measured against the
# edge matrix it let `C:\Users\legal\Documents\MSA` and `\\fileserver\legal\MSA` through.
_INTERNAL_LOCATOR = re.compile(
    r"[/\\]"                                               # POSIX/Windows/UNC separator
    r"|\b\w+\.(?i:md|pdf|docx?|txt|json|ya?ml|html?|csv)\b"  # filename + extension
    r"|\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b"                   # an ENV_VAR_STYLE token
    r"|\b(?i:repositor(?:y|ies))\b")                        # a reviewer's note


def public_source_name(source_document: object) -> str:
    """The reader-facing name of the paper, with every internal locator removed.

    Order matters and is the whole subtlety. Parentheticals are dropped FIRST,
    because `LIABILITY-MSA-001` reads "Legal Mind — Legal Constitution, Lawyer Review
    Version L1.5 (docs/…\u200b.md; owner ruling …)" — an em-dash split first would see the
    marker in segment two and truncate the name to "Legal Mind". Only then is the
    em-dash tail dropped, at the first segment carrying a locator, which is where
    "— MSA.pdf at LEGALMIND_SOURCE_MATERIAL_DIR" lives.

    Non-string input returns "" rather than raising: `chunk_ratified_standards`
    validates the field's presence and type before calling this, so "" is unreachable
    in practice and is a belt, not the brace.
    """
    if not isinstance(source_document, str):
        return ""
    name = re.sub(r"\s*\([^()]*\)",
                  lambda m: "" if _locator_match(_INTERNAL_LOCATOR, m.group())
                  else m.group(),
                  source_document)
    kept: list[str] = []
    for segment in name.split(" — "):
        if _locator_match(_INTERNAL_LOCATOR, segment):
            break
        kept.append(segment)
    return " — ".join(kept).strip(" ,;:")


class PositionEgressRefused(Exception):
    """A position span carries an internal locator and must not be sent anywhere.

    `AM-67` r7 / `AM-30` t4/t5. Raised rather than sanitised at the seam on purpose: a
    locator reaching this point means the corpus was NOT re-chunked after the 2026-09-15
    fix, and quietly cleaning it up would hide that. The correct response is to refuse
    the call, fall back to the verbatim quote (r8), and re-chunk.
    """


# The egress screen is NARROWER than `_INTERNAL_LOCATOR`, and the difference is load
# bearing. The sanitizer inspects `source_document` alone — a field that never contains
# prose — so it can treat any path separator as a locator. This screen inspects the
# COMPOSED span, which includes the ratified legal text, and measured against the real
# corpus a bare slash appears three times in perfectly ordinary legal English:
#
#     "§11 SLA / Service Levels"
#     "subject to the legal/compliance retention carve-out"
#     "31.14 A. Planned Full Service Discontinuation / Retirement"
#
# Refusing those would block the feature on the organization's own wording. What is
# actually diagnostic of an internal locator is an environment-variable token, a
# filename with a document extension, or the reviewer's repository note — none of which
# occurs in ratified prose. A repo path reaching here would carry an extension
# (`…LEGAL_CONSTITUTION_L1.10.md`) and is caught; an extensionless one is caught earlier
# by the sanitizer, which does screen bare separators.
_EGRESS_LOCATOR = re.compile(
    r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b"                    # ENV_VAR_STYLE token
    r"|\b\w+\.(?i:md|pdf|docx?|txt|json|ya?ml|html?|csv)\b"  # a filename
    r"|\b(?i:not named in this repositor(?:y|ies))\b")       # the reviewer's note


#: A Step 6 Document Type is SCREAMING_SNAKE too — `PARTNER_AGREEMENT`, `ORDER_FORM`,
#: `PRIVACY_POLICY` — and appears legitimately inside a requirement code
#: (`TERM-CONSEQUENCES-PARTNER_AGREEMENT-001`) and in composed chunk text. It is public
#: vocabulary, not an internal locator, so the ENV_VAR_STYLE arm must not fire on it.
#: Latent until `AM-72`: every ratified standard happened to be typed MSA/NDA/TOS/SLA,
#: all initialisms, so the first multi-word type refused the WHOLE corpus at the egress
#: screen (one dirty span refuses the batch) and would have done the same the day an
#: `ORDER_FORM` standard was ratified.
_DOCUMENT_TYPE_TOKENS = frozenset(DOCUMENT_TYPES)


def _locator_match(pattern: re.Pattern, text: str) -> re.Match | None:
    """The first match that is a genuine internal locator, skipping document types."""
    for match in pattern.finditer(text or ""):
        if match.group() not in _DOCUMENT_TYPE_TOKENS:
            return match
    return None


def screen_for_egress(spans: list[str]) -> None:
    """Refuse any span carrying an internal locator, before it can leave.

    This is `AM-67` r7 made structural. The runbook says to re-chunk before enabling
    synthesis; this makes a stale corpus fail closed instead of relying on the runbook
    having been followed.

    One dirty span refuses the whole batch: there is no partial send, because the
    caller's fallback is to quote verbatim, which costs the reader nothing.
    """
    for span in spans:
        match = _locator_match(_EGRESS_LOCATOR, span or "")
        if match:
            raise PositionEgressRefused(
                f"position span carries an internal locator ({match.group()!r}) — the "
                "corpus has not been re-chunked since the 2026-09-15 sanitizer; run "
                "tools.chunk_standards before enabling AM-67 synthesis")


def _compose_content(payload: dict) -> str:
    """The chunk text — the ratified file's own verbatim fields, nothing authored.

    The identifying prefix (code, clause, type) is what makes "what is our
    arbitration policy?" findable by lexical search; the quote is the answer a
    Domain A result renders verbatim (r4).

    The source document's name is NOT here (positions-verbatim-2, 2026-09-18). It is
    provenance, not position, and `content_tsv` is generated from this text, so it was
    INDEXED: "Legal Constitution, Lawyer Review Version L1.10" put `constitut` in 15
    of 40 chunks, and "what is written about partner agreement in the constitution"
    cleared the two-lexeme floor on that boilerplate plus `agreement` (df 21) — three
    MSA positions dressed as the answer to a question about a paper the corpus holds
    no position for. The name still lives in the ratified file's `source_document`,
    and the reader's header already shows code · clause · type · version.
    """
    parts = [
        f"{payload['requirement_code']}",
        f"{payload['source_clause']}",
        # The READABLE type, never the raw code: this string is rendered to a reader,
        # and a `WORD_WORD` code trips the egress screen's internal-locator test.
        # NOTE: the source document name is deliberately NOT composed in here — see
        # the docstring above (positions-verbatim-2, 2026-09-18) and
        # `test_the_source_name_is_provenance_and_is_no_longer_indexed`, which already
        # pins `public_source_name(...) not in content`. An earlier version of this
        # hunk (pre-rebase) appended it; dropped during the #91 rebase onto #98 to keep
        # that already-merged, tested invariant intact — flagged in the PR, not silent.
        f"({readable_document_type(payload['configuration']['document_type'])})",
        payload["source_quote"],
    ]
    return " ".join(p for p in parts if p)


def _published_version(db: DBSession, code: str) -> M.CompanyStandardVersion | None:
    """The current standard version for a code — the import tool's own resolution."""
    req = db.execute(
        select(M.Requirement).where(M.Requirement.code == code)
    ).scalars().first()
    if req is None:
        return None
    latest_rv = db.execute(
        select(M.RequirementVersion)
        .where(M.RequirementVersion.requirement_id == req.id)
        .order_by(M.RequirementVersion.version_number.desc())
        .limit(1)).scalars().first()
    if latest_rv is None:
        return None
    return db.execute(
        select(M.CompanyStandardVersion)
        .where(M.CompanyStandardVersion.requirement_version_id == latest_rv.id)
        .order_by(M.CompanyStandardVersion.version_number.desc())
        .limit(1)).scalars().first()


def chunk_ratified_standards(db: DBSession, *,
                             directory: Path | None = None) -> list[str]:
    """(Re)build Domain A chunks from the ratified files against the imported rows.

    Refuses (rather than skips) a file whose standard is not imported, or one
    missing its verbatim fields — a silently-skipped position would be a search
    surface that quietly lies about coverage.
    """
    schema = config.assist_schema()
    src = directory or RATIFIED_STANDARDS_DIR
    files = sorted(src.glob("*.json"))
    if not files:
        raise PositionChunkingRefused(f"no ratified standards in {src}")

    report: list[str] = []
    for path in files:
        payload = json.loads(path.read_text())
        code = payload.get("requirement_code")
        for field in ("requirement_code", "source_quote", "source_clause",
                      "source_document"):
            value = payload.get(field)
            # The type check is not pedantry: a non-string `source_document` used to
            # reach `public_source_name` and raise TypeError deep in the chunker.
            # Refusing here keeps the house rule — a malformed file is refused by name,
            # never skipped and never half-chunked.
            if not value or not isinstance(value, str):
                raise PositionChunkingRefused(
                    f"{path.name}: missing or malformed {field!r} — a position chunk "
                    "is composed of the ratified file's own verbatim fields and "
                    "cannot be invented (rule 21)")
        document_type = (payload.get("configuration") or {}).get("document_type")
        if not document_type:
            raise PositionChunkingRefused(
                f"{path.name}: missing configuration.document_type")

        version = _published_version(db, code)
        if version is None:
            raise PositionChunkingRefused(
                f"{path.name}: standard {code!r} has no imported "
                "company_standard_versions row — run "
                "tools.import_ratified_standards first")

        # r3 lifecycle: delete chunks of EVERY version of this standard's
        # requirement, then chunk the current version. CASCADE removes embeddings.
        db.execute(sql_text(f"""
            DELETE FROM "{schema}".position_chunks
            WHERE standard_code = :code
        """), {"code": code})

        db.execute(sql_text(f"""
            INSERT INTO "{schema}".position_chunks
                (id, standard_version_id, standard_code, document_type, ordinal,
                 content, source_clause, chunking_algorithm_version)
            VALUES (:id, :version_id, :code, :doc_type, 0, :content, :clause, :algo)
        """), {
            "id": str(uuid4()),
            "version_id": str(version.id),
            "code": code,
            "doc_type": document_type,
            "content": _compose_content(payload),
            "clause": payload["source_clause"],
            "algo": CHUNKING_ALGORITHM_VERSION,
        })
        report.append(f"{code}: chunked (version row {version.id})")

    # 53.3 discipline: counts and codes only, never standard text.
    log_event("assist.positions.chunked", count=len(report))
    embed_positions(db)
    return report


def embed_positions(db: DBSession) -> int:
    """Embed every position chunk that lacks a vector — `AM-32`'s
    `position_chunk_embeddings`, filled (2026-09-09) with the calibrated model.

    Best-effort in the sense `indexing._embed_chunks` gives the word: a missing model
    never fails chunking, because lexical retrieval works without vectors and the
    extractive answer's correctness never depends on them. What vectors add is
    RECALL for a paraphrased question — "how much notice ends the NDA early?" shares
    no lexeme with "terminated by either Party … thirty (30) days' notice" — and
    the calibrated gate decides whether a vector-only neighbour is evidence at all.
    """
    from legalmind.assist import calibration, embedding_runtime, store

    if not embedding_runtime.available():
        return 0
    schema = config.assist_schema()
    rows = db.execute(sql_text(f"""
        SELECT pc.id, pc.content FROM "{schema}".position_chunks pc
         WHERE NOT EXISTS (SELECT 1 FROM "{schema}".position_chunk_embeddings e
                            WHERE e.position_chunk_id = pc.id)
         ORDER BY pc.standard_code, pc.ordinal
    """)).all()
    if not rows:
        return 0
    vectors = embedding_runtime.embed_texts([r[1] for r in rows])
    if vectors is None:
        return 0
    identity = embedding_runtime.identity() or calibration.EMBEDDING_MODEL_REPO
    name, _, revision = identity.partition("@")
    model_id = store.register_embedding_model(
        db, name=name, version=revision or calibration.EMBEDDING_MODEL_REVISION,
        dimensions=calibration.EMBEDDING_DIMENSIONS,
        checksum=embedding_runtime.checksum_fragment() or "unrecorded")
    vtype = store.vector_type(db)
    db.execute(sql_text(f"""
        INSERT INTO "{schema}".position_chunk_embeddings
            (id, position_chunk_id, embedding_model_id, embedding)
        VALUES (:i, :c, :m, CAST(:v AS {vtype}))
        ON CONFLICT (position_chunk_id, embedding_model_id) DO NOTHING
    """), [{"i": str(uuid4()), "c": r[0], "m": model_id,
            "v": "[" + ",".join(f"{x:.6f}" for x in vec) + "]"}
           for r, vec in zip(rows, vectors, strict=True)])
    log_event("assist.positions.embedded", count=len(rows))
    return len(rows)


def search_positions(db: DBSession, *, query: str, permissions: frozenset[str],
                     limit: int = 10, embed_query=None,
                     topic: str | None = None) -> list[PositionHit]:
    """Domain A hybrid retrieval, authorization inside the function (r5).

    Without assist.ask AND (configuration.view OR legal_position.view) the result is
    [], exactly the shape an empty corpus returns — `AM-25` r6/r7. Lexical-first: a
    lexical hit is trusted on its own (the calibrated finding). The vector increment
    (2026-09-09) is the shared embedding machinery `AM-32` r9 names: the question's
    embedding is compared with the stored position vectors and neighbours are
    admitted only through the SAME calibrated gate the document retrieval uses
    (`calibration.gate_is_open` — floor plus peak margin), then fused with the
    lexical ranking by reciprocal rank. The extractive answer's correctness never
    depends on it; what it adds is recall for a paraphrase.

    ``embed_query`` is injectable for tests; by default the runtime's own callable.

    ``topic`` (2026-09-17) — a Constitution Appendix-B topic from the query planner.
    Applied INSIDE both queries as a further WHERE clause on the standard's own
    `configuration.constitution.topic` (the ratified file already carries it; nothing is
    denormalised onto the chunk — `AM-27` r4), so "what standards do we require for
    liability?" searches the liability standards rather than all forty. Authorization
    (r5) and the `AM-71` exclusion are unchanged and still inside the query. A topic
    that matches nothing falls back to the unfiltered search: narrowing may never turn
    an answer into a refusal.
    """
    # `AM-32` r5 as amended by `AM-44` (2026-09-08): `configuration.view` OR
    # `legal_position.view` — see `routing.positions_permitted` for the reasoning.
    if P.ASSIST_ASK not in permissions or not (
            P.CONFIGURATION_VIEW in permissions or P.LEGAL_POSITION_VIEW in permissions):
        return []
    schema = config.assist_schema()
    # OR-semantics with a match floor (2026-09-08). `plainto_tsquery` ANDs every
    # lexeme, so a natural question — "what is our approved position on widget
    # handling?" — matched nothing because "approved" and "position" are not in the
    # standard's text. The lexemes of the question are OR-ed instead, and a chunk
    # must share at least two of them (one, for a one-word question) so a single
    # common word never fetches the whole corpus. Ranked by matched lexemes, then
    # ts_rank, then code — deterministic for identical input.
    #
    # THE FLOOR COUNTS WORDS THE CORPUS DOES NOT USE — SO A SECOND PASS COUNTS
    # ONLY THE ONES IT DOES (2026-09-16).
    #
    # Reported live: "Explain our termination standard." answered "Information not
    # found in the organization's approved positions" while termination standards
    # are ratified and the Findings engine measures against them. The floor is
    # taken over EVERY lexeme of the question, including those that appear nowhere
    # in the corpus: {explain, termin, standard} is three lexemes, so two must
    # match, and every termination chunk shares exactly one — `termin`. Measured
    # document frequencies over the live 40 chunks: explain 0, standard 1,
    # termin 12. "What standards do we require for liability?" only worked by
    # accident: `LIABILITY-MSA-001`'s quote contains the word "standard".
    #
    # So when the strict floor finds NOTHING, the query runs again admitting a
    # chunk that shares at least one SUBJECT lexeme — a word this corpus uses in
    # more than one position (the `subject` CTE). That keeps the original
    # guarantee, which was that one incidental word must not fetch a position:
    # "Explain our standard." still retrieves nothing, because `standard` occurs
    # in exactly one quote and so is not a subject.
    #
    # A second pass rather than an `OR` in the first: every question that
    # retrieves anything today takes the identical path and gets the identical
    # ranking, so this can only convert a miss into an answer.
    #
    # ponytail: the subject test is df >= 2, which needs a topic to appear in two
    # positions. A subject held by exactly ONE standard is not rescued; upgrade to
    # "appears in the code or clause title" if that case ever shows up.
    #
    # THE INVERSE CASE HAS NOW SHOWN UP, and it gets worse as the corpus grows.
    # `AM-73` took the corpus 40 -> 79 chunks, and §31.4's quote ("a standard MSA")
    # took df(standard) from 1 to 2. `standard` is now a "subject", so "Explain our
    # standard." returns the liability cap and the tier standard where it previously
    # returned nothing. Two-of-seventy-nine is a much weaker claim to being a subject
    # than two-of-forty was, and the bar is absolute rather than proportional.
    # Measured noise, not a wrong legal answer — Domain A is extractive, so the reader
    # gets a verbatim quote and its citation — and the document-type filter above is
    # unaffected. Retuning this needs measurement across the whole question set, so it
    # is recorded rather than adjusted here.
    sql = sql_text(f"""
        WITH q AS (
            SELECT tsvector_to_array(to_tsvector('english', :q)) AS lex
        ), subject AS (
            SELECT COALESCE(array_agg(l), ARRAY[]::text[]) AS lex
              FROM q, unnest(q.lex) l
             WHERE (SELECT count(*) FROM "{schema}".position_chunks p2
                     WHERE tsvector_to_array(p2.content_tsv) @> ARRAY[l]) >= 2
        ), scored AS (
            SELECT pc.id, pc.standard_code, pc.document_type, pc.source_clause,
                   pc.content, csv.version_number, r.status::text AS ratification,
                   (SELECT count(*)
                      FROM q, unnest(tsvector_to_array(pc.content_tsv)) l
                     WHERE l = ANY(q.lex)) AS matched,
                   (SELECT count(*)
                      FROM subject, unnest(tsvector_to_array(pc.content_tsv)) l
                     WHERE l = ANY(subject.lex)) AS subject_matched,
                   ts_rank(pc.content_tsv,
                           to_tsquery('english', (SELECT array_to_string(lex, ' | ')
                                                    FROM q))) AS score
              FROM "{schema}".position_chunks pc
              JOIN company_standard_versions csv ON csv.id = pc.standard_version_id
              JOIN requirement_versions rv ON rv.id = csv.requirement_version_id
              JOIN requirements r ON r.id = rv.requirement_id
             WHERE (SELECT cardinality(lex) FROM q) > 0
               -- `AM-71` (AB-23, owner 2026-09-16): Ask retrieves ONLY currently
               -- active ratified standards. A retired standard is not a weaker
               -- answer to be labelled and shown; it is not an answer. Labelling
               -- it "Superseded" tells the reader, which is a mitigation, not the
               -- decision — the owner ruled it must not surface in normal
               -- retrieval at all. The chunks are deliberately NOT deleted: they
               -- stay for explicit version, history and audit use, which is why
               -- this is a read-side filter rather than a narrower chunker.
               AND r.status <> 'DEPRECATED'
               AND (CAST(:topic AS text) IS NULL
                    OR csv.configuration->'constitution'->>'topic' = :topic)
        )
        SELECT id, standard_code, document_type, source_clause, content, score, matched,
               version_number, ratification
          FROM scored
         WHERE CASE WHEN :relax THEN subject_matched >= 1
                    ELSE matched >= LEAST(2, (SELECT cardinality(lex) FROM q)) END
         ORDER BY matched DESC, score DESC, standard_code
         LIMIT :limit
    """)
    params = {"q": query, "limit": limit, "topic": topic}
    rows = db.execute(sql, {**params, "relax": False}).all()
    if not rows:
        rows = db.execute(sql, {**params, "relax": True}).all()
    lexical = [PositionHit(position_chunk_id=r.id, standard_code=r.standard_code,
                           document_type=r.document_type, source_clause=r.source_clause,
                           content=r.content, score=float(r.score),
                           standard_version=r.version_number,
                           ratification_status=r.ratification)
               for r in rows]
    vector = _vector_neighbours(db, query, limit=limit, embed_query=embed_query,
                                topic=topic)
    # THE SEMANTIC BRANCH IS THE RELEVANCE SIGNAL; THE LEXICAL BRANCH IS RECALL COVER.
    #
    # Measured on the live 40-standard corpus, 2026-09-16: within the lexical branch
    # `ts_rank` is flat and carries almost no signal. For "what is the termination
    # notice period?" FORCE-MAJEURE-MSA-001 and CURE-PERIOD-MSA-001 both score 0.0608 —
    # identical to each other and indistinguishable from CONVENIENCE-NOTICE-MSA-001 at
    # 0.0456. The ordering is driven by shared-lexeme COUNT (2 or 3 for everything), not
    # by relevance. The 2026-09-02 retrieval audit reached the same place from the other
    # direction: the lexical branch alone recovers 0.016.
    #
    # So fusing it into a gated semantic result does not add recall, it adds rank noise
    # — and RRF then promotes that noise into the three positions a reader is shown.
    # When the gated vector branch has found anything, it decides. Lexical stands in
    # only when there is no semantic signal at all: no model provisioned, or the
    # calibrated gate shut. That keeps the paraphrase recall the vector branch was added
    # for, and keeps lexical as the fallback it is, without comparing two score scales
    # that were never comparable.
    #
    # A SHUT GATE IS NOT (YET) A VERDICT HERE — measured 2026-09-18. Treating it as one
    # refused "Explain our termination standard." on the live corpus: that question sits
    # at top cosine 0.454 against four termination positions, UNDER the 0.5 floor that
    # was calibrated for one document's chunks, not forty short standards. Real
    # paraphrases landed at 0.45–0.47, junk at 0.29–0.39. That is a Domain A calibration
    # gap for the owner to see, not a constant to invent from ten points. Junk on an
    # unheld subject is stopped upstream instead: provenance is no longer indexed, and
    # `named_document_type` filters a paper we hold no position for.
    hits = _fuse([] if vector else lexical, vector, limit)
    # THE READER NAMED A KIND OF PAPER — SO ONLY POSITIONS ABOUT THAT PAPER ANSWER.
    #
    # Unlike the `topic` narrowing below, this one MAY end in a refusal, and that is
    # the point: a position about another document type is not a weaker answer to be
    # ranked lower, it is a wrong one (rule 15). Where the type IS covered this only
    # removes off-type noise; where it is not covered at all — every Constitution §31
    # type today — the empty result becomes the refusal that names what is covered,
    # which is the honest answer and the one a reader can act on.
    named = named_document_type(query)
    if named is not None:
        hits = [hit for hit in hits if hit.document_type == named]
    if topic is not None and not hits:
        # Narrowing may never turn an answer into a refusal (rule 15's direction is
        # the other way). A topic the corpus does not hold — or a plan that misread the
        # question — simply costs one more query.
        log_event("assist.positions.topic_fallback", topic=topic, level=logging.DEBUG)
        return search_positions(db, query=query, permissions=permissions, limit=limit,
                                embed_query=embed_query, topic=None)
    log_event("assist.positions.searched", hits=len(hits), lexical=len(lexical),
              vector=len(vector), topic=topic or "", level=logging.DEBUG)
    return hits


def _vector_neighbours(db: DBSession, query: str, *, limit: int,
                       embed_query=None, topic: str | None = None) -> list[PositionHit]:
    """Gated nearest neighbours over `position_chunk_embeddings`. [] when no model
    is available, when nothing is embedded, or when the calibrated gate stays shut."""
    from legalmind.assist import calibration, embedding_runtime, store

    embed = embed_query or embedding_runtime.embed_query
    embedded = embed(query) if query and query.strip() else None
    if embedded is None:
        return []
    vector, _identity = embedded
    schema = config.assist_schema()
    op = f'OPERATOR("{store.vector_schema(db)}".<=>)'
    vtype = store.vector_type(db)
    literal = "[" + ",".join(f"{x:.6f}" for x in vector) + "]"
    rows = db.execute(sql_text(f"""
        SELECT pc.id, pc.standard_code, pc.document_type, pc.source_clause, pc.content,
               csv.version_number, r.status::text AS ratification,
               1 - (pe.embedding {op} CAST(:q AS {vtype})) AS cosine
          FROM "{schema}".position_chunk_embeddings pe
          JOIN "{schema}".position_chunks pc ON pc.id = pe.position_chunk_id
          JOIN company_standard_versions csv ON csv.id = pc.standard_version_id
          JOIN requirement_versions rv ON rv.id = csv.requirement_version_id
          JOIN requirements r ON r.id = rv.requirement_id
         -- `AM-71` — the same exclusion as the lexical path. Both, or a retired
         -- position returns through whichever one is not filtered.
         WHERE r.status <> 'DEPRECATED'
           AND (CAST(:topic AS text) IS NULL
                OR csv.configuration->'constitution'->>'topic' = :topic)
         ORDER BY pe.embedding {op} CAST(:q AS {vtype}), pc.standard_code
         LIMIT :lim
    """), {"q": literal, "lim": max(limit, calibration.RETRIEVAL_TOP_K),
           "topic": topic}).all()
    scores = [float(r.cosine) for r in rows]
    if not calibration.gate_is_open(False, scores):
        return []
    return [PositionHit(position_chunk_id=r.id, standard_code=r.standard_code,
                        document_type=r.document_type, source_clause=r.source_clause,
                        content=r.content, score=float(r.cosine),
                        standard_version=r.version_number,
                        ratification_status=r.ratification)
            for r in rows if float(r.cosine) >= calibration.EVIDENCE_COSINE_FLOOR][:limit]


def _fuse(lexical: list[PositionHit], vector: list[PositionHit],
          limit: int) -> list[PositionHit]:
    """Reciprocal rank fusion (`calibration.RRF_K`). An exact tie goes to the vector
    side: a gated
    cosine is a stronger relevance signal than two shared lexemes (measured live: a
    liability standard sharing "agreement" and "give" with a notice question tied
    with the notice standard the vector had ranked first, and an alphabetical
    tie-break put liability on top). Deterministic: insertion order breaks ties."""
    from legalmind.assist.calibration import RRF_K

    fused: dict[UUID, float] = {}
    by_id: dict[UUID, PositionHit] = {}
    for rank, hit in enumerate(vector, start=1):
        key = hit.position_chunk_id
        fused[key] = fused.get(key, 0.0) + 1 / (RRF_K + rank)
        by_id.setdefault(hit.position_chunk_id, hit)
    for rank, hit in enumerate(lexical, start=1):
        key = hit.position_chunk_id
        fused[key] = fused.get(key, 0.0) + 1 / (RRF_K + rank)
        by_id.setdefault(hit.position_chunk_id, hit)
    order = list(fused)
    ordered = sorted(order, key=lambda i: (-fused[i], order.index(i)))
    return [by_id[i] for i in ordered[:limit]]

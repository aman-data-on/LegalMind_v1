"""System B of the RAG framework A/B benchmark: LegalMind's Ask rebuilt on LlamaIndex.

BENCHMARK ONLY. Production never imports this module. It needs llama-index-core and
llama-index-retrievers-bm25, which are not in requirements.txt. They are installed in an
isolated venv (`--system-site-packages`, so the backend's own packages are the ones
production runs). See docs/00-project/RAG_FRAMEWORK_AB_BENCHMARK.md § Configuration.

What is held equal to A (docs/00-project/RAG_FRAMEWORK_AB_CRITERIA.md):
  corpus     the same rows A searches (position_chunks, knowledge_items PARAGRAPHs,
             statute_chunks, document chunks), with the same authorization and status
             filters: DEPRECATED standards, UNRATIFIED or non-CURRENT-source
             Constitution text, WITHDRAWN Acts and quarantined folded sections are
             never loaded; a document's chunks are visible only to its own conversation
  vectors    the stored MiniLM vectors A searches, never re-embedded; queries through
             `embedding_runtime.embed_query`, the same model
  depth      50 candidates per retriever (A's `retrieval.DEPTH`), rerank depth 30, and
             evidence size 8 (A's floor in `retrieval.evidence_size`)
  reranker   A's cross-encoder (`rerank.scores`)
  floor      A's per-domain relevance floors (`evidence.RELEVANCE_FLOOR`)
  LLM        `generation.generate_raw`: the single egress seam, the same pinned model,
             temperature 0, the same gate and payload screens
  prompt     A's `BUNDLE_PROMPT_TEMPLATE`, excerpts labelled by kind as A labels them
  verifier   A's NLI claim verifier (`verify.check_answer`); a failing sentence is
             dropped, and an answer with none left is refused
  context    prior USER questions only; `AM-58` forbids an earlier answer in a payload,
             so LlamaIndex's default chat history (which includes answers) is not used

What B0 does NOT have, and is the subject of the measurement: LegalMind's router, query
planner, exact-reference lanes, kind-aware diversity selection, evidence bundle, claim
contracts and social/scope handling. B1 keeps all of those and swaps only the
per-domain candidate search (`retrieval._search`) for LlamaIndex retrievers.
"""
from __future__ import annotations

import dataclasses
import json
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from llama_index.core import VectorStoreIndex
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.llms import CompletionResponse, CustomLLM, LLMMetadata
from llama_index.core.llms.callbacks import llm_completion_callback
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.retrievers import QueryFusionRetriever
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode
from llama_index.retrievers.bm25 import BM25Retriever
from sqlalchemy import text

from legalmind import config
from legalmind.assist import (
    embedding_runtime,
    evidence,
    generation,
    guardrails,
    query_plan,
    rerank,
    retrieval,
    routing,
    verify,
)
from legalmind.assist import statutes as statute_corpus
from legalmind.assist.constitution import SOURCE_TYPE

DEPTH = retrieval.DEPTH
RERANK_DEPTH = retrieval.RERANK_DEPTH
EVIDENCE_K = 8
CONST, POS, STAT, DOC = (retrieval.CONSTITUTION, routing.Domain.POSITIONS.value,
                         routing.Domain.STATUTES.value, routing.Domain.DOCUMENT.value)
REFUSAL = "I couldn't find an answer in the available sources, so I won't guess."


# ---------------------------------------------------------------- framework adapters
class LegalMindEmbedding(BaseEmbedding):
    """The production query embedder behind LlamaIndex's interface. Nodes carry their
    stored vectors, so only queries are embedded."""

    def _get_query_embedding(self, query: str) -> list[float]:
        out = embedding_runtime.embed_query(query)
        if out is None:
            raise RuntimeError("embedding model not provisioned")
        return list(out[0])

    def _get_text_embedding(self, text_: str) -> list[float]:
        return self._get_query_embedding(text_)

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return self._get_query_embedding(query)


class CrossEncoderRerank(BaseNodePostprocessor):
    """A's cross-encoder as a LlamaIndex node postprocessor, scoring each retrieved
    child against its PARENT context (the framework's parent-document pattern). A's
    evidence floors were calibrated on parent context (`AM-87` r4), so the scores
    must be read there. The head is scored and the tail is kept unscored."""

    depth: int = RERANK_DEPTH
    context: Any = None                  # node -> parent text; None = the node itself

    def _postprocess_nodes(self, nodes, query_bundle=None):
        head, tail = nodes[:self.depth], nodes[self.depth:]
        scores = rerank.scores(statute_corpus.with_agency_names(query_bundle.query_str),
                               [self.context(n.node) if self.context else _scored_text(n.node)
                                for n in head])
        if scores is None:
            raise RuntimeError("reranker not provisioned")
        ranked = sorted(zip(head, scores, strict=True), key=lambda p: -p[1])
        return [NodeWithScore(node=n.node, score=s) for n, s in ranked] + [
            NodeWithScore(node=n.node, score=float("-inf")) for n in tail]


class GeminiSeamLLM(CustomLLM):
    """The single egress seam (`generation.generate_raw`) as a LlamaIndex LLM — same
    model, same gate, same payload screens, same usage counting."""

    prompt_version: str = "rag-ab-framework-1"
    max_output_tokens: int = 900

    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(model_name=generation._model(), num_output=self.max_output_tokens)

    @llm_completion_callback()
    def complete(self, prompt: str, formatted: bool = False, **kw) -> CompletionResponse:
        r = generation.generate_raw(prompt, prompt_version=self.prompt_version,
                                    environment=config.environment(),
                                    max_output_tokens=self.max_output_tokens)
        return CompletionResponse(text=r.text, raw={
            "prompt_tokens": r.prompt_tokens, "output_tokens": r.output_tokens,
            "latency_ms": r.latency_ms, "model": r.model, "finish": r.finish_reason})

    @llm_completion_callback()
    def stream_complete(self, prompt: str, formatted: bool = False, **kw):
        raise NotImplementedError("no token streaming: verification runs first (AM-25 r5)")


# LlamaIndex resolves an unset LLM or embedder to OpenAI — a second egress path that
# `AM-30` t1 forbids. Pin both, so no framework default can reach the network.
from llama_index.core import Settings  # noqa: E402

Settings.llm = GeminiSeamLLM()
Settings.embed_model = LegalMindEmbedding()


def _scored_text(node) -> str:
    note = node.metadata.get("note") or ""
    return f"{note}. {node.text}" if note else node.text


# ---------------------------------------------------------------- the corpus
def _vec(v) -> list[float]:
    return json.loads(v) if isinstance(v, str) else list(v)


def load_nodes(db) -> dict[str, list[TextNode]]:
    """Every row A could return, as LlamaIndex nodes with their stored vectors and A's
    reference format in metadata. The authorization and status predicates are A's own
    (see the module docstring); nothing A filters out is loaded."""
    s = config.assist_schema()
    nodes: dict[str, list[TextNode]] = defaultdict(list)

    def add(domain, rid, content, emb, **meta):
        nodes[domain].append(TextNode(
            id_=str(rid), text=content, embedding=_vec(emb),
            metadata={"domain": domain, **meta},
            excluded_embed_metadata_keys=list({"domain", *meta}),
            excluded_llm_metadata_keys=list({"domain", *meta})))

    for r in db.execute(text(f"""
            SELECT i.id, i.parent_id, i.section_path, i.content, i.authority, i.status,
                   i.ordinal, e.embedding
              FROM "{s}".knowledge_items i
              JOIN "{s}".knowledge_sources src ON src.id = i.source_id
              JOIN "{s}".knowledge_item_embeddings e ON e.knowledge_item_id = i.id
             WHERE src.source_type = :t AND src.status = 'CURRENT'
               AND i.kind = 'PARAGRAPH' AND i.status <> 'UNRATIFIED'"""),
            {"t": SOURCE_TYPE}):
        add(CONST, r.id, r.content, r.embedding, ref=f"CONST:{r.section_path}",
            parent=str(r.parent_id), authority=r.authority, status=r.status,
            group=str(r.parent_id), ord=r.ordinal)
    for r in db.execute(text(f"""
            SELECT pc.id, pc.standard_code, pc.content, pc.document_type, e.embedding
              FROM "{s}".position_chunks pc
              JOIN "{s}".position_chunk_embeddings e ON e.position_chunk_id = pc.id
              JOIN company_standard_versions csv ON csv.id = pc.standard_version_id
              JOIN requirement_versions rv ON rv.id = csv.requirement_version_id
              JOIN requirements r ON r.id = rv.requirement_id
             WHERE r.status <> 'DEPRECATED'""")):
        add(POS, r.id, r.content, r.embedding, ref=f"POS:{r.standard_code}",
            authority="COMPANY_STANDARD", status="CURRENT", group=str(r.id), ord=0,
            document_type=r.document_type)
    sql = f"""
            WITH {statute_corpus._QUARANTINE_CTE.format(
                schema=s, cap=statute_corpus.MAX_CHUNKS_PER_SECTION)}
            SELECT sc.id, s.official_title, s.status, sc.section_number, sc.marginal_note,
                   sc.content, sc.ordinal, e.embedding
              FROM "{s}".statute_chunks sc
              JOIN "{s}".statutes s ON s.id = sc.statute_id
              JOIN "{s}".statute_chunk_embeddings e ON e.statute_chunk_id = sc.id
             WHERE {statute_corpus._NOT_SUSPECT}"""
    for r in db.execute(text(sql)):
        auth, status = _statute_authority(r.official_title, r.status)
        add(STAT, r.id, r.content, r.embedding,
            ref=f"STAT:{r.official_title.removeprefix('The ')}:{r.section_number}",
            authority=auth, status=status, note=r.marginal_note or "",
            title=r.official_title, group=f"{r.official_title}:{r.section_number}",
            ord=r.ordinal)
    for r in db.execute(text(f"""
            SELECT c.id, c.document_version_id, c.content, c.evidence_id, c.ordinal,
                   e.embedding
              FROM "{s}".chunks c JOIN "{s}".chunk_embeddings e ON e.chunk_id = c.id""")):
        add(DOC, r.id, r.content, r.embedding, ref=f"DOC:{r.id}",
            document_version_id=str(r.document_version_id), authority="DOCUMENT",
            status="CURRENT", group=str(r.evidence_id), ord=r.ordinal)
    return dict(nodes)


def _statute_authority(title: str, status: str) -> tuple[str, str]:
    from legalmind.assist import authority
    auth, stat = authority.of_statute(title)
    return auth, ("REPEALED" if status == "REPEALED" else stat)


# ---------------------------------------------------------------- retrievers
@dataclass
class Corpus:
    nodes: dict[str, list[TextNode]]
    embed: BaseEmbedding = field(default_factory=LegalMindEmbedding)
    _cache: dict = field(default_factory=dict)
    build_s: float = 0.0

    def retriever(self, domain: str, *, document_version_id: str | None = None,
                  include_repealed: bool = False) -> QueryFusionRetriever | None:
        """Framework-standard hybrid: a vector index and BM25 over the same nodes,
        fused by reciprocal rank (`QueryFusionRetriever`, one query, so no LLM)."""
        key = (domain, document_version_id, include_repealed)
        if key in self._cache:
            return self._cache[key]
        pool = [n for n in self.nodes.get(domain, [])
                if (domain != DOC or n.metadata["document_version_id"] == document_version_id)
                and (include_repealed or n.metadata.get("status") != "REPEALED")]
        if not pool:
            self._cache[key] = None
            return None
        t = time.perf_counter()
        vec = VectorStoreIndex(pool, embed_model=self.embed).as_retriever(
            similarity_top_k=DEPTH)
        bm25 = BM25Retriever.from_defaults(nodes=pool, similarity_top_k=min(DEPTH, len(pool)))
        fused = QueryFusionRetriever([vec, bm25], similarity_top_k=DEPTH, num_queries=1,
                                     mode="reciprocal_rerank", use_async=False)
        self.build_s += time.perf_counter() - t
        self._cache[key] = fused
        return fused

    def parent_text(self, node) -> str:
        """A child's parent context, as A's read-time expanders build it
        (`retrieval.with_context`): a Constitution paragraph's siblings, a statute
        chunk's whole section, a document chunk with its ±1 neighbours in the same
        evidence row; the hit first, 4000 characters at most (`CONTEXT_CHARS`)."""
        if "groups" not in self._cache:
            g: dict = defaultdict(list)
            for ns in self.nodes.values():
                for n in ns:
                    g[(n.metadata["domain"], n.metadata["group"])].append(n)
            for v in g.values():
                v.sort(key=lambda n: n.metadata["ord"])
            self._cache["groups"] = g
        m = node.metadata
        sibs = self._cache["groups"][(m["domain"], m["group"])]
        if m["domain"] == DOC:
            sibs = [n for n in sibs if abs(n.metadata["ord"] - m["ord"]) <= 1]
        body, size = [node.text], len(node.text)
        for n in sibs:
            if n.node_id != node.node_id and size + len(n.text) <= retrieval.CONTEXT_CHARS:
                body.append(n.text)
                size += len(n.text)
        note = m.get("note") or ""
        return (f"{note}. " if note else "") + "\n".join(body)

    def search(self, domain: str, query: str, **kw) -> list[NodeWithScore]:
        r = self.retriever(domain, **kw)
        if r is None:
            return []
        seen, out = set(), []
        for n in r.retrieve(query):              # one place per source, as A does
            ref = n.node.metadata["ref"]
            if ref not in seen:
                seen.add(ref)
                out.append(n)
        return out


def candidate(n: NodeWithScore, domain: str) -> retrieval.Candidate:
    m = n.node.metadata
    from uuid import UUID
    return retrieval.Candidate(domain, m["ref"], UUID(n.node.node_id), n.node.text,
                               float(n.score or 0.0), m.get("authority", ""),
                               m.get("status", "CURRENT"), note=m.get("note", ""))


# ---------------------------------------------------------------- B0: framework-native
@dataclass
class Retrieved:
    pool: list[str]                      # fused + reranked candidate refs, all domains
    shown: list[str]                     # what reaches generation
    nodes: list[NodeWithScore]           # the shown nodes, in order
    ms: dict = field(default_factory=dict)


AUTHORIZED = (CONST, POS, STAT)          # PERMISSIONS of the benchmark persona


def b0_retrieve(corpus: Corpus, question: str, document_version_id: str | None = None
                ) -> Retrieved:
    """Every authorized domain searched (the framework has no router), one fused list
    across domains, the cross-encoder over its head, A's floors, top EVIDENCE_K."""
    t0 = time.perf_counter()
    retrievers = [corpus.retriever(d) for d in AUTHORIZED]
    if document_version_id:
        retrievers.append(corpus.retriever(DOC, document_version_id=document_version_id))
    retrievers = [r for r in retrievers if r is not None]
    fused = QueryFusionRetriever(retrievers, similarity_top_k=DEPTH * len(retrievers),
                                 num_queries=1, mode="reciprocal_rerank", use_async=False)
    seen, merged = set(), []
    for n in fused.retrieve(question):
        if n.node.metadata["ref"] not in seen:
            seen.add(n.node.metadata["ref"])
            merged.append(n)
    t1 = time.perf_counter()
    # A's rerank budget: RERANK_DEPTH per searched domain (A reranks each domain's head).
    ranked = CrossEncoderRerank(depth=RERANK_DEPTH * len(retrievers),
                                context=corpus.parent_text).postprocess_nodes(
        merged, query_bundle=QueryBundle(question))
    t2 = time.perf_counter()
    floor = evidence.RELEVANCE_FLOOR
    shown = [n for n in ranked
             if n.score is not None and n.score >= floor.get(n.node.metadata["domain"],
                                                             float("inf"))][:EVIDENCE_K]
    return Retrieved([n.node.metadata["ref"] for n in ranked],
                     [n.node.metadata["ref"] for n in shown], shown,
                     {"retrieval": round((t1 - t0) * 1000), "rerank": round((t2 - t1) * 1000)})


def _kind(n: NodeWithScore) -> str:
    return retrieval.kind_of(candidate(n, n.node.metadata["domain"]))


def render(nodes: list[NodeWithScore]) -> str:
    """A's excerpt labelling (kind, and the company's reading of the law) and A's
    citation names — the reader-facing parts of A's render, without parts or [A]/[M]."""
    from legalmind.assist import answer as answer_mod
    out = []
    for i, n in enumerate(nodes, 1):
        m = n.node.metadata
        label = ("LAW — the company's reading of the law, not the law itself"
                 if m.get("authority") == "SECONDARY_REFERENCE"
                 else answer_mod._KIND_LABEL[_kind(n)])
        where = _citation_name(m["ref"])
        status = "" if m.get("status") in ("CURRENT", None) else f" · {m['status']}"
        out.append(f"[{i}] {label} · {where}{status}\n{n.node.text.strip()}")
    return "\n\n".join(out)


def _citation_name(ref: str) -> str:
    if ref.startswith("CONST:"):
        return f"Legal Constitution L1.10 §{ref[6:]}"
    if ref.startswith("POS:"):
        return f"Company Standard {ref[4:]}"
    if ref.startswith("STAT:"):
        act, _, sec = ref[5:].rpartition(":")
        return f"{act}, s. {sec}" if sec[:1].isdigit() else f"{act}, {sec}"
    return "the document in scope"


CONDENSE = """Given the earlier questions in a conversation and a follow-up question, \
rewrite the follow-up as one standalone question. Keep every name, number and condition \
the reader gave. If the follow-up already stands alone, return it unchanged. Reply with \
the question only.

EARLIER QUESTIONS:
{history}

FOLLOW-UP: {question}

STANDALONE QUESTION:"""


@dataclass
class Turn:
    text: str
    answered: bool
    cited: list[str]
    shown: list[str]
    pool: list[str]
    standalone: str
    calls: int = 0
    prompt_tokens: int = 0
    output_tokens: int = 0
    ms: dict = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    draft: str = ""


_MARK = re.compile(r"\[(\d{1,2})\]")


class B0Chat:
    """A framework-native conversational engine (condense → retrieve → synthesize →
    verify), one per conversation. Memory holds the user's questions only (`AM-58`)."""

    def __init__(self, corpus: Corpus, *, document_version_id: str | None = None,
                 llm: CustomLLM | None = None):
        self.corpus, self.doc = corpus, document_version_id
        self.llm = llm or GeminiSeamLLM()
        self.questions: list[str] = []

    def _complete(self, prompt: str, turn: Turn) -> str:
        r = self.llm.complete(prompt)
        raw = r.raw or {}
        turn.calls += 1
        turn.prompt_tokens += raw.get("prompt_tokens") or 0
        turn.output_tokens += raw.get("output_tokens") or 0
        return r.text

    def ask(self, question: str) -> Turn:
        t0 = time.perf_counter()
        turn = Turn("", False, [], [], [], question)
        if self.questions:
            turn.standalone = self._complete(CONDENSE.format(
                history="\n".join(f"- {q}" for q in self.questions[-2:]),
                question=question), turn).strip() or question
        self.questions.append(question)
        got = b0_retrieve(self.corpus, turn.standalone, self.doc)
        turn.shown, turn.pool, turn.ms = got.shown, got.pool, dict(got.ms)
        if not got.nodes:
            turn.text = REFUSAL
            turn.ms["total"] = round((time.perf_counter() - t0) * 1000)
            return turn
        context = (f"\n{generation.CONTEXT_HEADER}\n"
                   + "\n".join(f"- {q}" for q in self.questions[:-1][-2:]) + "\n"
                   if len(self.questions) > 1 else "")
        prompt = generation.BUNDLE_PROMPT_TEMPLATE.format(
            bundle=render(got.nodes), question=question, context=context)
        tg = time.perf_counter()
        draft = self._complete(prompt, turn)
        turn.ms["generation"] = round((time.perf_counter() - tg) * 1000)
        turn.draft = draft
        tv = time.perf_counter()
        kept, turn.failures = verified(draft, got.nodes)
        turn.ms["verify"] = round((time.perf_counter() - tv) * 1000)
        if kept:
            turn.text, turn.answered = renumber(kept, got.nodes)
            turn.cited = cited_refs(turn.text, got.nodes, renumbered=True)
        else:
            turn.text = REFUSAL
        turn.ms["total"] = round((time.perf_counter() - t0) * 1000)
        return turn


def verified(draft: str, nodes: list[NodeWithScore]) -> tuple[list[str], list[str]]:
    """A's claim verifier sentence by sentence; anything it does not pass is dropped
    (unmarked, unsupported, contradicted, wrong kind). NOT FOUND is a refusal."""
    body = (draft or "").strip()
    if not body or body.upper().startswith("NOT FOUND"):
        return [], ["model: not found"]
    sents = [s.strip() for s in guardrails._SENTENCES.split(body) if s.strip()]
    marked = [s for s in sents if _MARK.search(s)]
    fails = [f"no citation: {s[:60]!r}" for s in sents if not _MARK.search(s)]
    if not marked:
        return [], fails
    ev = [n.node.text for n in nodes]
    kinds = [_kind(n) for n in nodes]
    auths = [n.node.metadata.get("authority", "") for n in nodes]
    res = verify.check_answer(" ".join(marked), ev, kinds, auths, marked)
    if res.judgements == [] and res.failures:
        return [], fails + res.failures             # verifier unavailable: fail closed
    # A SUPPORTED sentence carries the citations the verifier assigns (`j.citations`),
    # as A applies them in `verify.check_answer`: the model's own marker may name an
    # excerpt that does not state the figure while another shown excerpt does.
    keep = [_MARK.sub("", j.sentence).rstrip(" .") + " "
            + "".join(f"[{n}]" for n in (j.citations or j.cited)) + "."
            for j in res.judgements if j.verdict == "SUPPORTED" and not j.kind_error]
    fails += [f"{j.verdict.lower()}: {j.sentence[:60]!r}" for j in res.judgements
              if j.verdict != "SUPPORTED" or j.kind_error]
    return keep, fails


def renumber(sentences: list[str], nodes) -> tuple[str, bool]:
    order: list[int] = []
    for s in sentences:
        for m in _MARK.findall(s):
            if 1 <= int(m) <= len(nodes) and int(m) not in order:
                order.append(int(m))
    body = " ".join(_MARK.sub(lambda m: f"[{order.index(int(m.group(1))) + 1}]"
                              if int(m.group(1)) in order else "", s) for s in sentences)
    legend = "\n".join(f"[{i}] {_citation_name(nodes[n - 1].node.metadata['ref'])}"
                       for i, n in enumerate(order, 1))
    return f"{body}\n\nSources\n{legend}", True


def cited_refs(text_: str, nodes, *, renumbered: bool) -> list[str]:
    order: list[int] = []
    for s in [text_.split("\n\nSources")[0]]:
        for m in _MARK.findall(s):
            if int(m) not in order:
                order.append(int(m))
    if renumbered:                                # legend order is the cited order
        names = [ln.split("] ", 1)[1] for ln in text_.split("\n\nSources\n", 1)[1].splitlines()]
        by_name = {}
        for n in nodes:
            by_name.setdefault(_citation_name(n.node.metadata["ref"]), []).append(
                n.node.metadata["ref"])
        out = []
        for nm in names:
            for r in by_name.get(nm, []):
                if r not in out:
                    out.append(r)
                    break
        return out
    return [nodes[i - 1].node.metadata["ref"] for i in order if 1 <= i <= len(nodes)]


# ---------------------------------------------------------------- B1: hybrid
def b1_install(corpus: Corpus):
    """Swap A's per-domain candidate search for LlamaIndex retrievers, keeping
    everything around it: the router, plan, exact-reference lane, fusion across
    sub-queries, rerank, selection and bundle. A's Constitution search collapses to the
    best child per parent and reports the parent's authorities; B1 does the same from
    node metadata, because that is LegalMind domain logic, not retrieval. The document
    gate is A's calibrated gate, computed by A on the reader's own question, because no
    framework component replaces it. Returns an undo callable."""
    original = retrieval._search

    def _search(db, domain, query, *, permissions, route, document_version_id,
                embed_query, pool=None, question="", pinned_evidence=(), outline=False):
        if domain == DOC and (outline or document_version_id is None):
            return original(db, domain, query, permissions=permissions, route=route,
                            document_version_id=document_version_id,
                            embed_query=embed_query, pool=pool, question=question,
                            pinned_evidence=pinned_evidence, outline=outline)
        if domain == DOC and pool is not None and query == question:
            original(db, domain, query, permissions=permissions, route=route,
                     document_version_id=document_version_id, embed_query=embed_query,
                     pool=pool, question=question, pinned_evidence=pinned_evidence)
        hits = corpus.search(domain, query,
                             document_version_id=str(document_version_id)
                             if domain == DOC else None,
                             include_repealed=domain == STAT and route.include_superseded)
        if domain == POS:
            # A's scope filter on the paper the reader names (`named_document_type`),
            # as a metadata filter: a Partner Agreement question gets Partner positions.
            from legalmind.assist import positions
            named = positions.named_document_type(query)
            if named is not None:
                hits = [n for n in hits if n.node.metadata.get("document_type") == named]
        if domain == CONST:
            held: dict[str, set] = defaultdict(set)
            for n in hits:
                held[n.node.metadata["parent"]].add(n.node.metadata["authority"])
            out, parents = [], set()
            for n in hits:
                p = n.node.metadata["parent"]
                if p in parents:
                    continue
                parents.add(p)
                out.append(dataclasses.replace(candidate(n, domain),
                                               authorities=tuple(sorted(held[p]))))
            return out
        return [candidate(n, domain) for n in hits]

    retrieval._search = _search
    return lambda: setattr(retrieval, "_search", original)


def replay_citations(corpus: Corpus, rec: dict, document_version_id: str | None) -> dict:
    """Zero-provider replay of a stored B0 answer through the FIXED `verified`: the
    same deterministic retrieval for its stored standalone question, the same stored
    sentences, the verifier's own citation assignment. Words are never changed and a
    dropped sentence never returns. Refuses (returns None) if retrieval differs."""
    got = b0_retrieve(corpus, rec["standalone"], document_version_id)
    if got.shown != rec["shown"]:
        return {"replay": "retrieval_mismatch"}
    body = rec["text"].split("\n\nSources")[0]
    idx = {r: i + 1 for i, r in enumerate(got.shown)}

    def back(m):
        k = int(m.group(1))
        return f"[{idx[rec['cited'][k - 1]]}]" if 1 <= k <= len(rec["cited"]) else ""
    kept, fails = verified(_MARK.sub(back, body), got.nodes)
    if not kept:
        return {"replay": "nothing_verified", "failures": fails[:4]}
    text_, _ = renumber(kept, got.nodes)
    return {"replay": "ok", "text": text_,
            "cited": cited_refs(text_, got.nodes, renumbered=True)}


__all__ = [
    "REFUSAL",
    "B0Chat",
    "Corpus",
    "b0_retrieve",
    "b1_install",
    "load_nodes",
    "query_plan",
]

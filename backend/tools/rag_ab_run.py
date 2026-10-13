"""RAG framework A/B benchmark: freeze, run, score and report.

    python3 -m tools.rag_ab_run freeze                       # once, before any B result
    <venv>/python -m tools.rag_ab_run retrieval --db <scratch> --system A|B0|B1
    <venv>/python -m tools.rag_ab_run answers   --db <scratch> --system A|B0 [--live]
    python3 -m tools.rag_ab_run report

One frozen dataset (`tests/assist_eval/rag_ab/benchmark_v1.json` pins the SHA-256 of
every input), one scorer, the same configuration for every system. Criteria were
registered before B existed: docs/00-project/RAG_FRAMEWORK_AB_CRITERIA.md.

`retrieval` makes zero Gemini calls: the evidence each system would hand to generation,
scored per gold slot with `rag_benchmark.score_case`, the same function for every
system. `answers` runs whole conversations. Without `--live`, a stub model answers
offline, so every check runs at zero cost. With `--live` there is one real run, through
the single egress seam (the Gemini cost guard).

Full transcripts (the question, retrieved refs, answer text and every check) are
written OUTSIDE the repository, to LEGALMIND_AB_PRIVATE (default
/root/.legalmind/bench-cache/rag_ab, mode 700): a document conversation's answer
quotes supplied contracts, one of them executed with a real counterparty (54.6). The
repository copy keeps everything except answer text from document-scoped turns, which
it replaces with a SHA-256.
"""
from __future__ import annotations

import argparse
import collections
import contextlib
import hashlib
import json
import os
import pathlib
import re
import sys
import time
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from tools import rag_benchmark as rb

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVAL = ROOT / "tests" / "assist_eval"
AB = EVAL / "rag_ab"
MANIFEST = AB / "benchmark_v1.json"
FROZEN = {"single_turn": EVAL / "rag_benchmark.json",
          "document_lane": EVAL / "questions_draft.json",
          "conversations": AB / "conversations_v1.json",
          "criteria": ROOT.parent / "docs" / "00-project" / "RAG_FRAMEWORK_AB_CRITERIA.md"}
PRIVATE = pathlib.Path(os.environ.get("LEGALMIND_AB_PRIVATE",
                                      "/root/.legalmind/bench-cache/rag_ab"))
RESULTS = AB / "results"
PERMISSIONS = rb.PERMISSIONS
rb.DOMAIN_OF.setdefault("DOC", "DOCUMENT")
#: Compliance-verdict language an answer may not use in its own voice (`AM-25`): the
#: narrow core of `guardrails._JUDGMENT_LANGUAGE`, without words the corpus itself uses
#: as labels ("acceptable position", "risk", "deviation"). Quoted from a cited source
#: is not a verdict, and is not counted.
VERDICT = re.compile(r"\b(?:compli(?:es|ant)|non-compliant|in compliance with (?:our|the) "
                     r"(?:standard|policy)|meets? (?:our|the) (?:standard|policy)|"
                     r"violat(?:es|ion of) (?:our|the) (?:standard|policy)|"
                     r"should (?:not )?accept)\b", re.I)


# ---------------------------------------------------------------- freeze
def _sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def freeze() -> dict:
    if MANIFEST.exists():
        raise SystemExit(f"{MANIFEST.name} exists: a frozen version is never rewritten — "
                         "bump the version instead")
    m = {"version": "rag-ab-v1", "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                              time.gmtime()),
         "files": {k: {"path": str(p.relative_to(ROOT.parent)), "sha256": _sha(p)}
                   for k, p in FROZEN.items()},
         "suites": {
             "single_turn": "all 82 rag_benchmark cases + the 54 CONTRACT questions of "
                            "questions_draft (44 ANSWERABLE, 10 NOT_FOUND)",
             "multi_turn": "every conversation in conversations_v1.json",
             "adversarial": "rag_benchmark categories L, M, N and every case with "
                            "must_not; document NOT_FOUND; conversations tagged "
                            "adversarial",
             "manager": "rag_benchmark GT-* (roadmap §0 golden question family) and "
                        "conversations tagged manager"}}
    MANIFEST.write_text(json.dumps(m, indent=1) + "\n")
    return m


def check_frozen() -> dict:
    m = json.loads(MANIFEST.read_text())
    bad = [k for k, p in FROZEN.items() if _sha(p) != m["files"][k]["sha256"]]
    if bad:
        raise SystemExit(f"frozen inputs changed since {m['frozen_at']}: {bad} — "
                         "results would not be comparable")
    return m


# ---------------------------------------------------------------- the dataset
def doc_versions(db) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, vid in db.execute(text("SELECT original_filename, id FROM document_versions "
                                     "ORDER BY created_at DESC")):
        out.setdefault(name, str(vid))
    return out


def doc_gold(db, questions: list[dict], versions: dict) -> dict[str, set[str]]:
    from tools.benchmark_retrieval import _chunks, _resolve_anchors
    exp, fails = _resolve_anchors(questions, {d: _chunks(db, v) for d, v in versions.items()})
    if fails:
        raise SystemExit("anchor resolution failed: " + "; ".join(fails))
    return {k: {f"DOC:{c}" for c in v} for k, v in exp.items()}


def load(db) -> tuple[list[dict], list[dict]]:
    """(single-turn items, conversations), every expectation resolved from its source."""
    cases = {c["id"]: c for c in json.loads(FROZEN["single_turn"].read_text())["cases"]}
    qs = [q for q in json.loads(FROZEN["document_lane"].read_text())["questions"]
          if q["category"] == "CONTRACT"]
    by_q = {q["id"]: q for q in qs}
    versions = doc_versions(db)
    dgold = doc_gold(db, qs, versions)
    items = []
    for c in cases.values():
        suites = ["single_turn"]
        if c["category"] in "LMN" or c["must_not"]:
            suites.append("adversarial")
        if c["id"].startswith("GT-"):
            suites.append("manager")
        items.append({"id": c["id"], "suites": suites, "category": c["category"],
                      "question": c["question"], "after": c.get("after"), "document": None,
                      "gold": c["gold"], "must_not": c["must_not"],
                      "answer": c.get("answer", {}),
                      "kind": "refuse" if c.get("answer", {}).get("refuse") else "answer"})
    for q in qs:
        nf = q["expected"] == "NOT_FOUND"
        items.append({"id": f"DOC-{q['id']}", "suites": ["single_turn", "document"]
                      + (["adversarial"] if nf else []), "category": "DOC",
                      "question": q["question"], "after": None, "document": q["document"],
                      "version": versions[q["document"]],
                      "gold": [] if nf else [sorted(dgold[q["id"]])], "must_not": [],
                      "answer": {}, "kind": "refuse" if nf else "answer",
                      "doc_not_found": nf})
    convs = json.loads(FROZEN["conversations"].read_text())["conversations"]
    for conv in convs:
        conv["version"] = versions.get(conv["document"]) if conv["document"] else None
        for i, t in enumerate(conv["turns"], 1):
            t["id"] = f"{conv['id']}.T{i}"
            t.setdefault("context_dependent", False)
            if "from_case" in t:
                c = cases[t["from_case"]]
                t.setdefault("gold", c["gold"])
                t.setdefault("must_not", c["must_not"])
                t["answer"] = c.get("answer", {})
            elif "doc_case" in t:
                nf = any(by_q[x]["expected"] == "NOT_FOUND" for x in t["doc_case"])
                t["gold"] = [] if nf else [sorted(set().union(*(dgold[x]
                                                                 for x in t["doc_case"])))]
                t["must_not"], t["answer"], t["doc_not_found"] = [], {}, nf
            else:
                t.setdefault("gold", [])
                t.setdefault("must_not", [])
                t.setdefault("answer", {})
    return items, convs


# ---------------------------------------------------------------- retrieval stage
def _a_document(db, question: str, version: str) -> tuple[list[str], list[str], set, bool]:
    """A's document conversation through the multi-source stages (benchmark_document_lane)."""
    from legalmind.assist import evidence, query_plan, retrieval, routing, statutes
    route = routing.plan(question, has_document=True, permissions=PERMISSIONS,
                         statutes_available=statutes.available(db),
                         statute_jurisdictions=statutes.jurisdictions(db))
    if route.general_knowledge or route.capability or route.comparison or route.unmet:
        return [], [], set(), True
    plan = query_plan.plan(question, has_document=True)
    pool = retrieval.rerank(retrieval.candidates(db, plan, route, permissions=PERMISSIONS,
                                                 document_version_id=uuid.UUID(version)),
                            plan)
    bundle = evidence.build(db, plan, pool, retrieval.select(pool, plan))
    return [s.ref for s in bundle.shown()], pool.refs(), pool.searched, False


def retrieve_item(system: str, db, item: dict, corpus=None):
    """(shown, pool, searched, short_circuit, ms) for one single-turn item."""
    t = time.perf_counter()
    if system == "B0":
        # The framework's conversational context needs a model call (condense); at zero
        # Gemini a follow-up is searched as asked, and the J cases are reported apart.
        from tools import rag_ab_framework as F
        got = F.b0_retrieve(corpus, item["question"], item.get("version"))
        out = (got.shown, got.pool, set(F.AUTHORIZED) | ({"DOCUMENT"} if item.get(
            "version") else set()), False)
    elif item["document"]:
        out = _a_document(db, item["question"], item["version"])
    else:
        out = rb.retrieve_pool(db, item, reranked=True, bundled=True)
    return (*out, round((time.perf_counter() - t) * 1000))


def run_retrieval(system: str, db) -> dict:
    items, _ = load(db)
    held = rb.corpus_refs(db)
    doc_refs = {r for i in items for s in i["gold"] for r in s if r.startswith("DOC:")}

    def exists(ref):
        return ref in doc_refs or any(rb.ref_matches(ref, h) for h in held)
    corpus, undo, prep = None, None, {}
    if system in ("B0", "B1"):
        from tools import rag_ab_framework as F
        t = time.perf_counter()
        corpus = F.Corpus(F.load_nodes(db))
        prep["load_nodes_s"] = round(time.perf_counter() - t, 2)
        if system == "B1":
            undo = F.b1_install(corpus)
    rows = []
    try:
        for item in items:
            shown, pool, searched, short, ms = retrieve_item(system, db, item, corpus)
            s = rb.score_case(item, shown, pool, searched, exists, short, const_indexed=True)
            s.update(suites=item["suites"], ms=ms, pool=pool[:60],
                     pool_ranks=[rb._rank(slot, pool) for slot in item["gold"]],
                     context_unresolved=bool(item.get("after")) and system == "B0")
            if item.get("doc_not_found"):
                s["must_refuse"] = True
                s["false_admission"] = any(r.startswith("DOC:") for r in shown)
            rows.append(s)
            print(system, item["id"], [x["rank"] for x in s["slots"]],
                  "WRONG" if s["wrong_source"] else "", flush=True)
    finally:
        if undo:
            undo()
    if corpus is not None:
        prep["index_build_s"] = round(corpus.build_s, 2)
    return {"system": system, "stage": "retrieval", "gemini_calls": 0,
            "manifest": check_frozen()["frozen_at"], "prep": prep,
            "metrics": {s: retrieval_metrics([r for r in rows if s in r["suites"]])
                        for s in ("single_turn", "document", "adversarial", "manager")}
            | {"no_document": retrieval_metrics([r for r in rows if r["category"] != "DOC"]),
               "follow_ups_J": retrieval_metrics([r for r in rows if r["category"] == "J"])},
            "rows": rows}


def retrieval_metrics(rows: list[dict]) -> dict:
    slots = [x["rank"] for r in rows for x in r["slots"]]
    pslots = [x for r in rows for x in r.get("pool_ranks", [])]

    def frac(xs):
        xs = list(xs)
        return round(sum(xs) / len(xs), 4) if xs else None

    def at(ranks, k):
        return frac(rk is not None and rk <= k for rk in ranks)
    ms = sorted(r["ms"] for r in rows) or [0]
    refuse = [r for r in rows if r["must_refuse"]]
    return {"cases": len(rows), "slots": len(slots),
            **{f"recall@{k}": at(slots, k) for k in (1, 3, 5, 10)},
            "mrr": frac(1 / rk if rk else 0 for rk in slots),
            "ndcg@5": frac(r["ndcg5"] for r in rows if r["ndcg5"] is not None),
            "multi_source_complete": frac(all(x["rank"] for x in r["slots"])
                                          for r in rows if len(r["slots"]) > 1),
            "wrong_source_cases": sum(bool(r["wrong_source"]) for r in rows),
            "wrong_source_rate": frac(bool(r["wrong_source"]) for r in rows),
            "false_admission": sum(r["false_admission"] for r in refuse),
            "must_refuse": len(refuse),
            **{f"pool_recall@{k}": at(pslots, k) for k in (1, 5, 10, 50)},
            "pool_mrr": frac(1 / rk if rk else 0 for rk in pslots),
            "ms_p50": ms[len(ms) // 2], "ms_p95": ms[int(len(ms) * .95)],
            "failure_codes": dict(collections.Counter(x["code"] for r in rows
                                                      for x in r["slots"] if x["code"]))}


# ---------------------------------------------------------------- answer stage
class Resolver:
    """ref -> the source text a citation points at, from the same tables both systems
    read (a Constitution section's paragraphs, a standard's chunks, an Act section's
    chunks, a document chunk)."""

    def __init__(self, db):
        self.db, self.cache = db, {}
        self.repealed = {t.removeprefix("The ") for t, in db.execute(text(
            'SELECT official_title FROM assist.statutes WHERE status = \'REPEALED\''))}
        self.chunk_doc = {f"DOC:{c}": str(v) for c, v in db.execute(text(
            "SELECT id, document_version_id FROM assist.chunks"))}

    def __call__(self, ref: str) -> str:
        if ref in self.cache:
            return self.cache[ref]
        kind, _, rest = ref.partition(":")
        q = {"CONST": ("SELECT string_agg(i.content, ' ' ORDER BY i.ordinal) FROM "
                       "assist.knowledge_items i JOIN assist.knowledge_sources s "
                       "ON s.id = i.source_id WHERE i.section_path = :a "
                       "AND s.status = 'CURRENT' AND i.kind = 'PARAGRAPH' "
                       "AND i.status <> 'UNRATIFIED'", {"a": rest}),
             "POS": ("SELECT string_agg(content, ' ') FROM assist.position_chunks "
                     "WHERE standard_code = :a", {"a": rest}),
             "DOC": ("SELECT content FROM assist.chunks WHERE id = CAST(:a AS uuid)",
                     {"a": rest})}.get(kind)
        if kind == "STAT":
            act, _, sec = rest.rpartition(":")
            q = ("SELECT string_agg(c.content, ' ' ORDER BY c.ordinal) FROM "
                 "assist.statute_chunks c JOIN assist.statutes s ON s.id = c.statute_id "
                 "WHERE regexp_replace(s.official_title, '^The ', '') = :a "
                 "AND c.section_number = :b", {"a": act, "b": sec})
        self.cache[ref] = (self.db.execute(text(q[0]), q[1]).scalar() or "") if q else ""
        return self.cache[ref]


def _frames(ref: str) -> list[str]:
    from legalmind.assist import query_plan as qp
    from legalmind.assist import verify
    kinds = {"POS": [qp.COMPANY_POSITION], "STAT": [qp.LAW], "DOC": [qp.CONTRACT],
             "CONST": [qp.COMPANY_POSITION, qp.HISTORICAL_EXCEPTION]}[ref.split(":")[0]]
    out = [verify.frame(k, "") for k in kinds]
    return out + ([verify.frame(qp.LAW, "SECONDARY_REFERENCE")] if ref.startswith("CONST")
                  else [])


def _sentences(body: str) -> list[str]:
    """Sentences, with a marker the model put after the full stop ("… notice. [5] Next")
    handed back to the sentence it belongs to; legend lines dropped."""
    from legalmind.assist import guardrails
    out: list[str] = []
    for s in (x.strip() for x in guardrails._SENTENCES.split(body or "")):
        lead = re.match(r"^((?:\[\d{1,2}\]\s*)+)(.*)$", s)
        if lead and out and lead.group(2):
            out[-1] += " " + lead.group(1).strip()
            s = lead.group(2).strip()
        if s and not re.fullmatch(r"(?:-\s*)?\[\d+\][^.]*", s):
            out.append(s)
    return out


def score_turn(t: dict, rec: dict, prior_cited: set[str], prior_qs: list[str],
               resolve: Resolver, scope_version: str | None) -> dict:
    """Every deterministic check on one answered turn. Accuracy fields are None on an
    expert_review turn; safety fields are always computed."""
    from legalmind.assist import answer as answer_mod
    from legalmind.assist import guardrails, verify
    cited = rec["cited"]
    body = rec["text"].split("\n\nSources")[0]
    sents = _sentences(body) if rec["answered"] else []
    texts = {r: resolve(r) for r in cited}
    asked_figs = set().union(*(guardrails._figures(q) for q in [t["q"], *prior_qs]))
    unsupported_fig, contradictions, verdicts, nli = [], [], [], []
    marked = 0
    for s in sents:
        nums = [int(n) for n in re.findall(r"\[(\d{1,2})\]", s)]
        refs = [cited[n - 1] for n in nums if 1 <= n <= len(cited)]
        pool = [texts[r] for r in refs] or list(texts.values())
        figs = guardrails._figures(s) - asked_figs
        if figs - set().union(*(guardrails._figures(x) for x in pool)) \
                and not answer_mod._ATTRIBUTED.search(s):
            unsupported_fig.append(s[:120])
        for phrase in t["answer"].get("must_not_state_as_policy", []):
            # Not a contradiction when the cited source itself states the figure
            # (Constitution §9 names an 18- or 24-month proposal as negotiable).
            if phrase.lower() in s.lower() and not (
                    answer_mod._NEGATION.search(s) or answer_mod._ABSENT.search(s)
                    or answer_mod._ATTRIBUTED.search(s)
                    or any(phrase.lower() in x.lower() for x in pool)):
                contradictions.append(s[:120])
        m = VERDICT.search(s)
        if m and not any(m.group(0).lower() in x.lower() for x in pool):
            verdicts.append(s[:120])
        if refs:
            marked += 1
            claim = re.sub(r"\[(\d{1,2}|A|M)\]", "", s).strip(" -")
            # Each premise framed by what its source IS, as the verifier frames it:
            # "the company position is X" is not entailed by a bare "X".
            pairs = [(f"{f} {p}", verify.content(claim)) for r in refs for f in _frames(r)
                     for p in verify.premises(claim, texts[r])[:3]]
            got = verify.entailment(pairs) if pairs else None
            if got:
                e, c = max(x[0] for x in got), max(x[1] for x in got)
                nli.append("SUPPORTED" if e >= .5 else "CONTRADICTED" if c >= .5
                           else "UNSUPPORTED")
    gold = [r for slot in t["gold"] for r in slot]
    hit = [r for r in cited if any(rb.ref_matches(g, r) for g in gold)]
    scored = t["kind"] in ("answer", "refuse")
    foreign = [r for r in cited if r.startswith("DOC:")
               and resolve.chunk_doc.get(r) != scope_version]
    non_current = [r for r in cited if r.startswith("STAT:")
                   and r[5:].rpartition(":")[0] in resolve.repealed
                   and not any(g.startswith("STAT:") and g[5:].rpartition(":")[0]
                               in resolve.repealed for g in gold)]
    out = {
        "answered": rec["answered"], "cited": cited, "shown": rec.get("shown", []),
        "sentences": len(sents), "marked_sentences": marked,
        "unsupported_figure": unsupported_fig, "contradictions": contradictions,
        "verdicts": verdicts, "nli": dict(collections.Counter(nli)),
        "wrong_source_cited": sorted({r for r in cited for m in t["must_not"]
                                      if rb.ref_matches(m, r)}),
        "wrong_source_shown": sorted({r for r in rec.get("shown", []) for m in t["must_not"]
                                      if rb.ref_matches(m, r)}),
        "foreign_document": foreign, "non_current_cited": non_current,
        "hard_negative_lead": bool(cited) and any(rb.ref_matches(h, cited[0])
                                                  for h in t.get("hard_negative_lead", [])),
    }
    kind = t["kind"]
    if kind == "answer" and gold and scored:
        out.update(cites_gold=bool(hit), citation_precision=round(len(hit) / len(cited), 4)
                   if cited else None, false_refusal=not rec["answered"],
                   slots_cited=round(sum(any(rb.ref_matches(g, r) for r in cited
                                             for g in slot) for slot in t["gold"])
                                     / len(t["gold"]), 4))
        if t.get("clarification_acceptable") and not rec["answered"]:
            out["false_refusal"] = None
    if kind == "refuse" or t.get("doc_not_found"):
        admitted = [r for r in cited if r.startswith("DOC:")] if t.get("doc_not_found") \
            else cited
        out["false_admission"] = rec["answered"] and bool(admitted)
    if kind in ("social", "off_scope"):
        out["answered_from_corpus"] = bool(cited)
    if kind == "cites_prior":
        out["cites_prior_ok"] = rec["answered"] and bool(set(cited) & prior_cited) \
            if prior_cited else None
    return out


def _a_turn(db, conv_id, version, question, captured) -> dict:
    from legalmind.assist import service
    from legalmind.assist.state import AssistAnswerState
    captured.clear()
    t = time.perf_counter()
    out = service.ask(db, conversation_id=conv_id,
                      document_version_id=uuid.UUID(version) if version else None,
                      question=question, permissions=PERMISSIONS,
                      request_id=f"rag-ab-{uuid.uuid4().hex[:8]}")
    db.commit()
    ms = round((time.perf_counter() - t) * 1000)
    tr, usage = captured.get("trace", {}), captured.get("usage", {})
    if tr.get("cited_refs"):
        cited = list(tr["cited_refs"])
    else:
        cited = [f"DOC:{c.chunk_id}" for c in out.citations]
        cited += [f"POS:{p['standard_code']}" for p in out.positions]
        cited += [f"STAT:{s['official_title'].removeprefix('The ')}:{s['section_number']}"
                  for s in (out.statutes or {}).get("citations", [])]
    body = out.text + (f"\n\n{out.statutes['text']}" if out.statutes
                       and out.statutes.get("text") else "")
    return {"text": body, "answered": out.answer_state == AssistAnswerState.ANSWERED,
            "state": out.answer_state.value, "cited": list(dict.fromkeys(cited)),
            "shown": tr.get("evidence_refs", cited), "path": tr.get("path"),
            "fallback": tr.get("fallback_kind"), "calls": usage.get("calls", 0),
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0), "ms": ms,
            "stages_ms": captured.get("timings", {})}


def _stub_a():
    """Offline A: the multi-source call answers with eval_generation's deterministic
    stub; every other provider call (legacy answer, rescue judge) is unavailable, so
    those paths fail closed exactly as with no credential."""
    from legalmind.assist import generation
    from tools import eval_generation as eg

    def none(*a, **k):
        raise generation.GenerationUnavailable("offline benchmark run")
    generation.generate_contract_answer = eg.stub
    generation.generate_bundle_repair = eg.stub_repair
    generation.generate_raw = none


class _StubLLM:
    """Offline B: condense returns the follow-up; an answer restates each excerpt's
    first sentence with its marker. Exercises verification at zero cost."""

    def complete(self, prompt):
        r = type("R", (), {})()
        r.raw = {"prompt_tokens": len(prompt) // 4, "output_tokens": 0}
        if prompt.startswith("Given the earlier questions"):
            r.text = prompt.rsplit("FOLLOW-UP: ", 1)[1].split("\n")[0]
            return r
        parts = re.findall(r"^\[(\d+)\] [^\n]*\n(.+?)(?=\n\n\[\d+\] |\n\nQUESTION|\Z)",
                           prompt, re.S | re.M)
        out = []
        for n, body in parts:
            first = re.match(r"(.{20,300}?[.;:])(?:\s|$)", " ".join(body.split()))
            out.append(f"{(first.group(1) if first else body[:200]).rstrip('.;:')} [{n}].")
        r.text = " ".join(out) or "NOT FOUND"
        return r


def conversations_for(items, convs):
    """Single-turn items become one-turn conversations (a follow-up case asks its prior
    turn first, unscored), then the multi-turn set."""
    out = []
    for it in items:
        turns = []
        if it.get("after"):
            turns.append({"id": f"{it['id']}.prior", "q": it["after"], "kind": "prior",
                          "gold": [], "must_not": [], "answer": {}})
        turns.append({"id": it["id"], "q": it["question"], "kind": it["kind"],
                      "gold": it["gold"], "must_not": it["must_not"], "answer": it["answer"],
                      "doc_not_found": it.get("doc_not_found", False),
                      "context_dependent": bool(it.get("after"))})
        out.append({"id": it["id"], "suite": it["suites"], "document": it["document"],
                    "version": it.get("version"), "turns": turns, "single": True})
    for c in convs:
        out.append({**c, "single": False})
    return out


def run_answers(system: str, db, *, live: bool, only: list[str] | None) -> dict:
    items, convs = load(db)
    resolve = Resolver(db)
    todo = [c for c in conversations_for(items, convs) if not only or c["id"] in only]
    captured: dict = {}
    corpus = None
    if not live:
        if system == "A":
            _stub_a()
    elif not os.environ.get("LEGALMIND_GEMINI_API_KEY"):
        raise SystemExit("--live needs LEGALMIND_GEMINI_API_KEY")
    if system == "A":
        from legalmind.assist import service
        original = service._emit_trace

        def emit(trace, usage, timings, outcome, request_id, conversation_id):
            captured.update(trace=dict(trace), usage=dict(usage), timings=dict(timings))
            return original(trace, usage, timings, outcome, request_id, conversation_id)
        service._emit_trace = emit
        user = db.execute(text("SELECT id FROM users ORDER BY email LIMIT 1")).scalar()
    else:
        from tools import rag_ab_framework as F
        t = time.perf_counter()
        corpus = F.Corpus(F.load_nodes(db))
        load_s = time.perf_counter() - t
    out_convs = []
    for conv in todo:
        version = conv.get("version")
        if system == "A":
            from legalmind.assist import service
            contract = db.execute(text("SELECT contract_id FROM document_versions WHERE "
                                       "id = CAST(:v AS uuid)"), {"v": version}).scalar() \
                if version else None
            cid = service.create_conversation(db, user_id=user, contract_id=contract)
            db.commit()
        else:
            chat = F.B0Chat(corpus, document_version_id=version,
                            llm=None if live else _StubLLM())
        prior_cited: set[str] = set()
        prior_qs: list[str] = []
        turns = []
        for t in conv["turns"]:
            try:
                if system == "A":
                    rec = _a_turn(db, cid, version, t["q"], captured)
                else:
                    r = chat.ask(t["q"])
                    rec = {"text": r.text, "answered": r.answered, "cited": r.cited,
                           "shown": r.shown, "standalone": r.standalone, "calls": r.calls,
                           "prompt_tokens": r.prompt_tokens,
                           "output_tokens": r.output_tokens, "ms": r.ms.get("total"),
                           "stages_ms": r.ms, "failures": r.failures[:6], "draft": r.draft}
            except Exception as exc:                       # recorded, never hidden
                db.rollback()
                rec = {"text": "", "answered": False, "cited": [], "shown": [],
                       "error": f"{type(exc).__name__}: {exc}"[:200], "calls": 0,
                       "prompt_tokens": 0, "output_tokens": 0, "ms": None}
            checks = score_turn(t, rec, prior_cited, prior_qs, resolve, version) \
                if t["kind"] != "prior" else {}
            turns.append({"id": t["id"], "q": t["q"], "kind": t["kind"],
                          "context_dependent": t.get("context_dependent", False),
                          "expert_review": t["kind"] == "expert_review",
                          "outcome_expert_review": t.get("outcome_expert_review", False),
                          "reason": t.get("reason"), **rec, "checks": checks})
            prior_cited |= set(rec["cited"])
            prior_qs.append(t["q"])
            print(system, t["id"], "ANS" if rec["answered"] else "---", rec["cited"][:3],
                  rec.get("error", ""), flush=True)
        out_convs.append({"id": conv["id"], "suite": conv["suite"],
                          "document": conv["document"], "single": conv["single"],
                          "turns": turns})
    res = {"system": system, "stage": "answers", "live": live,
           "manifest": check_frozen()["frozen_at"], "model": _model(),
           "conversations": out_convs}
    if corpus is not None:
        res["prep"] = {"load_nodes_s": round(load_s, 2), "index_build_s": round(corpus.build_s, 2)}
    res["metrics"] = answer_metrics(res)
    return res


def rescore(system: str, db, *, live: bool, replay: bool = False) -> dict:
    """Re-run every check on stored answers (zero provider calls): a scorer fix never
    needs a second paid run."""
    name = f"benchmark_results_{system}{'' if live else '_offline'}.json"
    res = json.loads((PRIVATE / name).read_text())
    items, convs = load(db)
    specs = {t["id"]: (c, t) for c in conversations_for(items, convs) for t in c["turns"]}
    resolve = Resolver(db)
    corpus = None
    if replay:
        from tools import rag_ab_framework as F
        corpus = F.Corpus(F.load_nodes(db))
    for conv in res["conversations"]:
        if corpus is not None:
            version = specs[conv["turns"][0]["id"]][0].get("version")
            for t in conv["turns"]:
                if t["answered"] and "cited_before_replay" not in t:
                    got = F.replay_citations(corpus, t, version)
                    t["replay"] = got["replay"]
                    if got["replay"] == "ok":
                        t["text_before_replay"], t["cited_before_replay"] = t["text"], t["cited"]
                        t["text"], t["cited"] = got["text"], got["cited"]
                    print("replay", t["id"], got["replay"], flush=True)
        prior_cited: set[str] = set()
        prior_qs: list[str] = []
        for t in conv["turns"]:
            c, spec = specs[t["id"]]
            if t["kind"] != "prior":
                t["checks"] = score_turn(spec, t, prior_cited, prior_qs, resolve,
                                         c.get("version"))
            prior_cited |= set(t["cited"])
            prior_qs.append(t["q"])
    res["metrics"] = answer_metrics(res)
    res["rescored_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    write(res, name)
    return res


def _model() -> str:
    from legalmind.assist import generation
    return generation._model()


def _suite_turns(res, suite):
    for c in res["conversations"]:
        if suite == "multi_turn" and c["single"]:
            continue
        if suite in c["suite"] or (suite == "multi_turn" and not c["single"]):
            yield from (t for t in c["turns"] if t["kind"] != "prior")


def answer_metrics(res: dict) -> dict:
    def frac(xs):
        xs = [x for x in xs if x is not None]
        return round(sum(xs) / len(xs), 4) if xs else None
    out = {}
    for suite in ("single_turn", "multi_turn", "adversarial", "manager", "document"):
        ts = list(_suite_turns(res, suite))
        ck = [t["checks"] for t in ts]
        scored = [t for t in ts if not t["expert_review"] and "cites_gold" in t["checks"]]
        nli = collections.Counter()
        for c in ck:
            nli.update(c.get("nli", {}))
        ms = sorted(t["ms"] for t in ts if t.get("ms")) or [0]
        calls = [t.get("calls") or 0 for t in ts]
        out[suite] = {
            "turns": len(ts), "scored_answer_turns": len(scored),
            "expert_review_turns": sum(t["expert_review"] for t in ts),
            "errors": sum(bool(t.get("error")) for t in ts),
            "answered_rate": frac(t["answered"] for t in ts),
            "cites_gold": frac(t["checks"]["cites_gold"] for t in scored),
            "slots_cited": frac(t["checks"]["slots_cited"] for t in scored),
            "citation_precision": frac(t["checks"]["citation_precision"] for t in scored),
            "false_refusals": sum(bool(t["checks"].get("false_refusal")) for t in scored),
            "context_dependent_cites_gold": frac(t["checks"]["cites_gold"] for t in scored
                                                 if t["context_dependent"]),
            "must_refuse": sum("false_admission" in c for c in ck),
            "false_admissions": sum(bool(c.get("false_admission")) for c in ck),
            "social_or_scope_answered_from_corpus": sum(bool(c.get("answered_from_corpus"))
                                                        for c in ck),
            "social_or_scope_turns": sum("answered_from_corpus" in c for c in ck),
            "cites_prior_ok": frac(c.get("cites_prior_ok") for c in ck),
            "wrong_source_cited": sum(bool(c.get("wrong_source_cited")) for c in ck),
            "wrong_source_shown": sum(bool(c.get("wrong_source_shown")) for c in ck),
            "contradictions": sum(len(c.get("contradictions", [])) for c in ck),
            "verdict_language": sum(len(c.get("verdicts", [])) for c in ck),
            "foreign_document_cited": sum(bool(c.get("foreign_document")) for c in ck),
            "non_current_cited": sum(bool(c.get("non_current_cited")) for c in ck),
            "hard_negative_lead": sum(bool(c.get("hard_negative_lead")) for c in ck),
            "unsupported_figure_sentences": sum(len(c.get("unsupported_figure", []))
                                                for c in ck),
            "sentences": sum(c.get("sentences", 0) for c in ck),
            "nli_marked": dict(nli),
            "nli_supported_share": round(nli["SUPPORTED"] / sum(nli.values()), 4)
            if nli else None,
            "latency_ms_p50": ms[len(ms) // 2], "latency_ms_p95": ms[int(len(ms) * .95)],
            "gemini_calls": sum(calls), "gemini_calls_per_turn": round(sum(calls)
                                                                      / max(1, len(ts)), 3),
            "prompt_tokens": sum(t.get("prompt_tokens") or 0 for t in ts),
            "output_tokens": sum(t.get("output_tokens") or 0 for t in ts),
        }
    return out


# ---------------------------------------------------------------- outputs
def write(res: dict, name: str) -> None:
    PRIVATE.mkdir(parents=True, exist_ok=True)
    os.chmod(PRIVATE, 0o700)
    (PRIVATE / name).write_text(json.dumps(res, indent=1, default=str))
    safe = json.loads(json.dumps(res, default=str))
    for c in safe.get("conversations", []):
        if c.get("document"):
            for t in c["turns"]:
                for k in ("text", "draft", "text_before_replay"):
                    if t.get(k):
                        t[k] = "sha256:" + hashlib.sha256(t[k].encode()).hexdigest()
                for k in ("unsupported_figure", "contradictions", "verdicts"):
                    if t.get("checks", {}).get(k):
                        t["checks"][k] = [f"<{len(t['checks'][k])} document-scoped "
                                          "sentences, private copy>"]
                t["failures"] = []
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / name).write_text(json.dumps(safe, indent=1) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=("freeze", "retrieval", "answers", "rescore",
                                        "report"))
    ap.add_argument("--db")
    ap.add_argument("--system", choices=("A", "B0", "B1"))
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--replay", action="store_true",
                    help="rescore B0 with the verifier's citation assignment (zero calls)")
    args = ap.parse_args(argv)
    if args.command == "freeze":
        print(json.dumps(freeze(), indent=1))
        return 0
    if args.command == "report":
        from tools import rag_ab_report
        return rag_ab_report.main()
    check_frozen()
    db = sessionmaker(bind=create_engine(args.db, future=True), future=True)()
    if args.command == "rescore":
        res = rescore(args.system, db, live=args.live, replay=args.replay)
        print(json.dumps(res["metrics"], indent=1))
        return 0
    if args.command == "retrieval":
        res = run_retrieval(args.system, db)
        db.rollback()
        write(res, f"retrieval_{args.system}.json")
        print(json.dumps(res["metrics"], indent=1))
    else:
        if args.system == "B1":
            raise SystemExit("B1 answers are run only if its retrieval stage passes "
                             "(cost guard) — see the report")
        res = run_answers(args.system, db, live=args.live, only=args.only)
        suffix = "" if args.live else "_offline"
        write(res, f"benchmark_results_{args.system}{suffix}.json")
        print(json.dumps(res["metrics"], indent=1))
    return 0


if __name__ == "__main__":
    with contextlib.suppress(BrokenPipeError):
        sys.exit(main())

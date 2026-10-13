"""A requirement anchor is embedded once per worker process, per model (2026-09-29).

Anchors are ratified standard wording only and identical for every analysis under a
snapshot; re-embedding all 72 each run was ~0.8 s of every report. Clauses are still
embedded every run — they are the document.
"""
import uuid

from legalmind.analysis import semantic
from legalmind.assist import embedding_runtime
from legalmind.mapping.engine import Clause


def test_anchors_are_embedded_once_per_model_and_clauses_every_run(monkeypatch):
    sent: list[list[str]] = []
    model = ["model-a"]
    monkeypatch.setattr(embedding_runtime, "identity", lambda: model[0])
    monkeypatch.setattr(embedding_runtime, "embed_texts",
                        lambda texts: sent.append(list(texts)) or [[1.0, float(len(t))]
                                                                   for t in texts])
    monkeypatch.setattr(semantic, "_ANCHOR_VECTORS", {})
    clause = Clause(uuid.uuid4(), "Each party's liability is capped.", None, None, 1, False)
    anchors = {uuid.uuid4(): "liability cap", uuid.uuid4(): "governing law"}

    first = semantic.build_index([clause], anchors)
    second = semantic.build_index([clause], anchors)
    assert sent == [[clause.content, "liability cap", "governing law"], [clause.content]]
    assert first.anchors == second.anchors and first.clause_vectors == second.clause_vectors

    model[0] = "model-b"                 # another model never reads model-a's vectors
    semantic.build_index([clause], anchors)
    assert sent[-1] == [clause.content, "liability cap", "governing law"]

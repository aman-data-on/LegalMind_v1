"""The embedding backend — `AM-26` r1/r4/r5 and `AM-30` t1.

Every test that needs weights **skips** when none are provisioned. That is deliberate,
not a gap: `AM-26` r5 forbids fetching weights at runtime, so a test that downloaded a
model to run itself would violate the rule it exists to check. CI provisions nothing, and
"cannot verify here" must never read as "verified".

The tests that need no weights — the network boundary and the contract's shape — run
everywhere, and they are the ones guarding the properties that matter most.
"""

from __future__ import annotations

import ast
import json
import pathlib

import pytest

from legalmind.assist import onnx_backend
from legalmind.assist.embedding import EmbeddingBackend, LexicalStrategy

_ANY_MODEL = "sentence-transformers__all-MiniLM-L6-v2"


def _provisioned() -> pathlib.Path | None:
    root = onnx_backend.model_root()
    if not root.exists():
        return None
    for candidate in sorted(root.glob("*/*/manifest.json")):
        return candidate.parent
    return None


@pytest.fixture
def model_dir():
    directory = _provisioned()
    if directory is None:
        pytest.skip("no model provisioned; AM-26 r5 forbids fetching weights at runtime")
    return directory


# ==========================================================================
# No weights required — the properties that matter most
# ==========================================================================
def test_the_backend_module_makes_no_network_call():
    """`AM-30` t1 — the generation call is the ONLY permitted egress.

    Asserted here as well as in `test_import_boundaries.py` because this module is the
    one most likely to acquire a download helper "for convenience". The first draft of
    it did exactly that, and the boundary test refused it; fetching now lives in
    `tools/provision_model.py`, outside the application package.
    """
    source = pathlib.Path(onnx_backend.__file__).read_text()
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not (imported & {"urllib", "requests", "httpx", "socket", "http"}), (
        f"{onnx_backend.__name__} imports a network client: "
        f"{sorted(imported & {'urllib', 'requests', 'httpx', 'socket', 'http'})}")


def test_only_the_cpu_execution_provider_is_permitted():
    """onnxruntime ships an `AzureExecutionProvider` that can reach a remote endpoint.

    Left to onnxruntime's default provider list, an inference session could acquire a
    second egress path — and `AM-30` t1 permits exactly one, the generation call. The
    list is pinned, and this asserts the pin rather than trusting the default.
    """
    assert onnx_backend.EXECUTION_PROVIDERS == ["CPUExecutionProvider"]


def test_a_batch_bound_exists_and_is_modest():
    """A memory bound, not a tuning knob.

    Embedding a whole document in one call reached 14 GB RSS and was OOM-killed:
    padding takes every sequence to the longest in the batch, so one long chunk inflates
    the whole batch's activations. Embeddings are position-independent, so batching
    changes no result — it only bounds the peak.
    """
    assert 1 <= onnx_backend.EMBED_BATCH <= 64


def test_the_lexical_strategy_satisfies_the_retrieval_contract():
    """The measurement baseline has to be comparable like-for-like with a candidate."""
    strategy = LexicalStrategy()
    assert strategy.label
    assert hasattr(strategy, "rank")


# ==========================================================================
# Weights required
# ==========================================================================
def test_the_backend_satisfies_the_embedding_contract(model_dir):
    backend = onnx_backend.OnnxEmbeddingBackend(model_dir)
    assert isinstance(backend, EmbeddingBackend)


def test_the_dimension_is_read_from_the_model_not_configured(model_dir):
    """`AM-26` r2 — the dimension is a property of the chosen weights.

    The schema follows the model, never the other way round. This is also why
    `chunk_embeddings` does not exist yet: pinning a column width before a model is
    selected would settle by DDL what the record settles by measurement.
    """
    backend = onnx_backend.OnnxEmbeddingBackend(model_dir)
    assert backend.dimensions > 0
    vectors = backend.embed(["a clause about liability"])
    assert len(vectors[0]) == backend.dimensions, (
        "the declared dimension must match the vectors actually produced")


def test_the_identity_names_a_pinned_revision(model_dir):
    """`AM-26` r4 — the version is recorded against every answer."""
    backend = onnx_backend.OnnxEmbeddingBackend(model_dir)
    assert "@" in backend.identity


def test_the_session_runs_on_cpu_only(model_dir):
    backend = onnx_backend.OnnxEmbeddingBackend(model_dir)
    assert backend.providers == ["CPUExecutionProvider"]


def test_a_tampered_model_file_is_refused(model_dir, tmp_path):
    """`AM-26` r5 — checksummed, and verified rather than assumed.

    A silently-swapped model produces vectors incomparable with every one already
    stored, and nothing downstream would notice: the numbers still look like numbers.
    So the check is at load time and it fails loudly.
    """
    import shutil

    copy = tmp_path / "model"
    shutil.copytree(model_dir, copy)
    (copy / "tokenizer.json").write_bytes(
        (copy / "tokenizer.json").read_bytes() + b" ")

    with pytest.raises(RuntimeError, match="checksum"):
        onnx_backend.OnnxEmbeddingBackend(copy)


def test_embedding_is_deterministic_for_a_fixed_model(model_dir):
    """Not `ENG-11` — `AM-28` r1 bars the assist lane from that gate.

    But re-embedding must not move vectors, or a stored embedding and a freshly computed
    query embedding stop being comparable and retrieval quietly degrades.
    """
    backend = onnx_backend.OnnxEmbeddingBackend(model_dir)
    first = backend.embed(["limitation of liability"])[0]
    second = backend.embed(["limitation of liability"])[0]
    assert first == second


def test_batching_does_not_change_a_vector(model_dir):
    """The bound exists for memory; it must not alter a result."""
    backend = onnx_backend.OnnxEmbeddingBackend(model_dir)
    text = "termination for convenience on ninety days notice"
    alone = backend.embed([text])[0]
    padding = ["unrelated filler text"] * (onnx_backend.EMBED_BATCH + 3)
    in_batch = backend.embed([text, *padding])[0]
    similarity = sum(a * b for a, b in zip(alone, in_batch, strict=True))
    assert similarity > 0.9999, (
        "a vector changed depending on what it was batched with; padding is leaking "
        "into the pooled representation")


def test_vectors_are_normalized(model_dir):
    """Cosine similarity reduces to a dot product, and pgvector's `<=>` then behaves
    consistently regardless of text length."""
    backend = onnx_backend.OnnxEmbeddingBackend(model_dir)
    for vector in backend.embed(["short", "a considerably longer clause of text here"]):
        norm = sum(v * v for v in vector) ** 0.5
        assert abs(norm - 1.0) < 1e-4


def test_semantically_closer_text_scores_higher(model_dir):
    """A floor, not a quality claim.

    If this fails the model or the pooling is wrong. Passing it says nothing about
    whether the model is *good* — that is what the benchmark measures, and why no model
    is selected on the strength of a unit test.
    """
    backend = onnx_backend.OnnxEmbeddingBackend(model_dir)
    liability, cap, termination = backend.embed([
        "limitation of liability", "cap on damages", "termination for convenience"])

    def cos(a, b):
        return sum(x * y for x, y in zip(a, b, strict=True))

    assert cos(liability, cap) > cos(liability, termination)


def test_the_manifest_records_repo_revision_and_checksums(model_dir):
    manifest = json.loads((model_dir / onnx_backend.MANIFEST).read_text())
    assert manifest["repo"] and manifest["revision"]
    assert len(manifest["model.onnx"]) == 64
    assert len(manifest["tokenizer.json"]) == 64

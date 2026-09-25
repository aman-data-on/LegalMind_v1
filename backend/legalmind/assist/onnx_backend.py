"""Local, self-hosted ONNX backends — `AM-26` r1, r4, r5, and `AM-30` t1.

Two of them, sharing every admissibility constraint the record imposes: the embedding
backend (bi-encoder, mean-pooled vectors) and the reranking backend (cross-encoder, one
relevance score per query/passage PAIR). `AM-25`'s permitted list names "hybrid retrieval
with reranking" and `AM-26`'s stack table names a "Reranking model | local, self-hosted,
open-weight, cross-encoder" — so the reranker needs no amendment, only r2's
smallest-that-passes selection and r4/r5's pin and checksum.

Neither names a model: the identity is a constructor argument, because `AM-26` r1
requires the model identity to be configuration and r2 requires the choice to be made by
measurement.

--------------------------------------------------------------------------
The execution provider is pinned, and that is a security control
--------------------------------------------------------------------------
onnxruntime ships an `AzureExecutionProvider` alongside `CPUExecutionProvider`. Left to
its default provider list, an inference session could in principle acquire a second
network egress path — and `AM-30` t1 permits exactly one, the generation call. So the
provider list is pinned to CPU explicitly and asserted by a test.

This is not defensiveness about an unlikely default. It is the same reasoning `AM-25` r2
applies to database grants: a boundary enforced by mechanism survives a future change
that a boundary enforced by expectation does not.

--------------------------------------------------------------------------
Weights: obtained once, checksummed, never fetched at runtime (`AM-26` r5)
--------------------------------------------------------------------------
**This module makes no network call, and cannot.** Fetching weights lives in
`tools/provision_model.py`, outside the application package, and that placement is the
point rather than tidiness: `tests/test_import_boundaries.py` asserts that **nothing**
under `legalmind/` imports a network client, and keeping that invariant absolute is
worth more than the convenience of a download helper sitting next to its consumer.

`AM-26` r5's "obtained once … never fetched at runtime" is therefore structural. The
first draft of this module did import `urllib` for a `provision()` helper, and the
boundary test refused it — which is what the test is for.

Loading verifies the SHA-256 of every file against the manifest written at provisioning
time, so a silently-swapped model fails loudly instead of producing vectors that are
incomparable with everything already stored.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib

# Pinned, and the only provider permitted. See the module docstring.
EXECUTION_PROVIDERS = ["CPUExecutionProvider"]

# Files an ONNX model needs. `model.onnx` lives under `onnx/` in the HuggingFace layout
# used by every candidate, embedding and cross-encoder alike.
# Public, because `tools/provision_model.py` writes what this module reads and the two
# must agree on the layout.
MODEL_FILES = ("onnx/model.onnx", "tokenizer.json")
MANIFEST = "manifest.json"

# Texts per forward pass. Not a tuning knob — a memory bound.
#
# Embedding a whole document in one call looks harmless (a few hundred short strings)
# and is not: padding takes every sequence to the longest in the batch, so a 236-chunk
# document with one 512-token chunk produces a (236, 512, hidden) activation tensor and
# the intermediate feed-forward tensors are several times larger again. Measured: that
# reached 14 GB RSS and was OOM-killed. 16 keeps a batch's activations in the tens of
# megabytes, and embeddings are position-independent so batching changes no result.
EMBED_BATCH = 16


def model_root() -> pathlib.Path:
    """Where provisioned weights live. Local, and outside the repository (54.6)."""
    return pathlib.Path(os.environ.get(
        "LEGALMIND_MODEL_DIR",
        str(pathlib.Path.home() / ".legalmind" / "models")))


def verify_manifest(directory: pathlib.Path) -> dict:
    """Every file the manifest records must match it — the graph, the tokenizer AND any
    external-data file a >2 GB model keeps its weights in (`AM-26` r5). Hashed in
    streamed blocks, so a multi-gigabyte weights file is never held in memory. A
    silently-swapped model would produce vectors incomparable with everything already
    stored, and nothing downstream would notice."""
    manifest = json.loads((directory / MANIFEST).read_text())
    for name, expected in manifest.items():
        if name in ("repo", "revision"):
            continue
        digest = hashlib.sha256()
        with (directory / name).open("rb") as handle:
            while block := handle.read(1 << 20):
                digest.update(block)
        if digest.hexdigest() != expected:
            raise RuntimeError(
                f"{name} does not match its recorded checksum in {directory}; "
                "the weights differ from what was provisioned")
    return manifest


class OnnxEmbeddingBackend:
    """An embedding model loaded from local, checksum-verified weights."""

    def __init__(self, directory: pathlib.Path, *, pooling: str = "mean",
                 max_length: int = 512):
        """`pooling` is how the model was trained to be read: "mean" (the
        sentence-transformers family — the production default), "cls" (BGE) or "last"
        (decoder embedders such as Qwen3, which read the final real token)."""
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self._np = np
        self._dir = pathlib.Path(directory)
        self._pooling = pooling
        self._max_length = max_length
        manifest = verify_manifest(self._dir)
        self._repo = manifest["repo"]
        self._revision = manifest["revision"]

        self._tokenizer = Tokenizer.from_file(str(self._dir / "tokenizer.json"))
        self._session = ort.InferenceSession(
            str(self._dir / "model.onnx"), providers=EXECUTION_PROVIDERS)
        self._inputs = {i.name for i in self._session.get_inputs()}
        self._cache_inputs = [i for i in self._session.get_inputs()
                              if i.name.startswith("past_key_values.")]
        # Read from the graph, never configured. `AM-26` r2 makes the dimension a
        # property of the chosen weights, and the schema follows it.
        self._dimensions = int(self._session.get_outputs()[0].shape[-1])

    @property
    def identity(self) -> str:
        return f"{self._repo}@{self._revision}"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def providers(self) -> list[str]:
        """The session's actual providers, so a test can assert CPU-only."""
        return list(self._session.get_providers())

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Mean-pooled, L2-normalized sentence embeddings.

        Mean pooling over the token dimension with the attention mask applied, which is
        what the sentence-transformers family of models is trained for. Normalized so
        cosine similarity reduces to a dot product — and so pgvector's `<=>` cosine
        distance behaves consistently regardless of text length.
        """
        np = self._np
        if not texts:
            return []

        self._tokenizer.enable_padding()
        self._tokenizer.enable_truncation(max_length=self._max_length)

        out: list[list[float]] = []
        for start in range(0, len(texts), EMBED_BATCH):
            batch = texts[start:start + EMBED_BATCH]
            encoded = self._tokenizer.encode_batch(batch)

            ids = np.array([e.ids for e in encoded], dtype=np.int64)
            mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
            feed = {"input_ids": ids, "attention_mask": mask,
                    "token_type_ids": np.zeros_like(ids),
                    "position_ids": np.clip(mask.cumsum(axis=1) - 1, 0, None)}
            feed = {k: v for k, v in feed.items() if k in self._inputs}
            # A decoder export (Qwen3) also takes a key/value cache; an embedding pass
            # has no past, so each is an EMPTY tensor shaped by the graph itself:
            # symbolic batch → this batch, symbolic past length → 0.
            for spec in self._cache_inputs:
                shape = [len(batch) if i == 0 else d if isinstance(d, int) else 0
                         for i, d in enumerate(spec.shape)]
                feed[spec.name] = np.zeros(shape, dtype=np.float32)

            hidden = self._session.run(None, feed)[0]
            if self._pooling == "cls":
                pooled = hidden[:, 0]
            elif self._pooling == "last":
                pooled = hidden[np.arange(len(batch)), mask.sum(axis=1) - 1]
            else:
                expanded = mask[..., None].astype(hidden.dtype)
                summed = (hidden * expanded).sum(axis=1)
                counts = np.clip(expanded.sum(axis=1), 1e-9, None)
                pooled = summed / counts
            norms = np.clip(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12, None)
            out.extend((pooled / norms).astype("float32").tolist())
        return out


# Query/passage pairs per forward pass. The same memory bound as `EMBED_BATCH` and for
# the same reason — padding takes every pair to the longest in the batch — but pairs are
# longer than chunks (query + passage in one sequence), so the batch is smaller.
RERANK_BATCH = 8


class OnnxCrossEncoderBackend:
    """A cross-encoder relevance model loaded from local, checksum-verified weights.

    The difference from the embedding backend is not the plumbing, which is identical
    (same provisioning tool, same manifest, same checksum verification, same pinned CPU
    provider), but what the model is asked: a bi-encoder embeds a query and a passage
    SEPARATELY and compares the vectors, so it never sees them together; a cross-encoder
    reads the pair as one sequence and scores it. That is why it ranks better and why it
    cannot be used to search — there is nothing to index.

    Scores are raw logits: monotonic, unbounded, and **not** comparable across models or
    calibrated to anything. They order a candidate list. Nothing here decides whether to
    answer — the calibrated gate in `calibration.py` does that, on the retrieval scores
    it was calibrated on — and a logit is never rendered to a reader (`AI-03` item 16).
    """

    def __init__(self, directory: pathlib.Path):
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self._np = np
        self._dir = pathlib.Path(directory)
        # `AM-26` r5 — verified, not assumed, exactly as for the embedding weights.
        manifest = verify_manifest(self._dir)
        self._repo = manifest["repo"]
        self._revision = manifest["revision"]

        self._tokenizer = Tokenizer.from_file(str(self._dir / "tokenizer.json"))
        self._session = ort.InferenceSession(
            str(self._dir / "model.onnx"), providers=EXECUTION_PROVIDERS)
        self._inputs = {i.name for i in self._session.get_inputs()}

    @property
    def identity(self) -> str:
        return f"{self._repo}@{self._revision}"

    @property
    def providers(self) -> list[str]:
        """The session's actual providers, so a test can assert CPU-only."""
        return list(self._session.get_providers())

    def score(self, query: str, passages: list[str]) -> list[float]:
        """One relevance score per passage, in the order given."""
        # A relevance cross-encoder emits one logit per pair; some export a two-column
        # head, where the positive class is column 1.
        return [float(row[0] if len(row) == 1 else row[-1])
                for row in self.pair_logits([(query, p) for p in passages])]

    def pair_logits(self, pairs: list[tuple[str, str]]) -> list[list[float]]:
        """The model's raw output row per (text_a, text_b) pair — one logit for a
        relevance model, one per label for an NLI model (PHASE 11, `AM-90`)."""
        np = self._np
        if not pairs:
            return []

        self._tokenizer.enable_padding()
        self._tokenizer.enable_truncation(max_length=512)

        out: list[list[float]] = []
        for start in range(0, len(pairs), RERANK_BATCH):
            batch = pairs[start:start + RERANK_BATCH]
            encoded = self._tokenizer.encode_batch(batch)

            ids = np.array([e.ids for e in encoded], dtype=np.int64)
            mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
            feed = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self._inputs:
                # A cross-encoder NEEDS these: they are what tells the model where the
                # query ends and the passage begins. Zeroing them (as the embedding
                # backend does, having only one segment) would silently degrade it.
                feed["token_type_ids"] = np.array(
                    [e.type_ids for e in encoded], dtype=np.int64)
            feed = {k: v for k, v in feed.items() if k in self._inputs}

            out.extend([float(x) for x in row]
                       for row in self._session.run(None, feed)[0])
        return out


"""A local, self-hosted embedding backend — `AM-26` r1, r4, r5, and `AM-30` t1.

One implementation of `EmbeddingBackend`, satisfying every admissibility constraint the
record imposes. It names no model: the identity is a constructor argument, because
`AM-26` r1 requires the model identity to be configuration and r2 requires the choice to
be made by measurement.

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

# Files an ONNX sentence-embedding model needs. `model.onnx` lives under `onnx/` in the
# HuggingFace layout used by every candidate.
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


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class OnnxEmbeddingBackend:
    """An embedding model loaded from local, checksum-verified weights."""

    def __init__(self, directory: pathlib.Path):
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self._np = np
        self._dir = pathlib.Path(directory)
        manifest = json.loads((self._dir / MANIFEST).read_text())
        self._repo = manifest["repo"]
        self._revision = manifest["revision"]

        # `AM-26` r5 — verified, not assumed. A silently-swapped model would produce
        # vectors incomparable with everything already stored, and nothing downstream
        # would notice.
        for name in ("model.onnx", "tokenizer.json"):
            actual = _sha256((self._dir / name).read_bytes())
            if actual != manifest[name]:
                raise RuntimeError(
                    f"{name} does not match its recorded checksum in {self._dir}; "
                    "the weights differ from what was provisioned")

        self._tokenizer = Tokenizer.from_file(str(self._dir / "tokenizer.json"))
        self._session = ort.InferenceSession(
            str(self._dir / "model.onnx"), providers=EXECUTION_PROVIDERS)
        self._inputs = {i.name for i in self._session.get_inputs()}
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
        self._tokenizer.enable_truncation(max_length=512)

        out: list[list[float]] = []
        for start in range(0, len(texts), EMBED_BATCH):
            batch = texts[start:start + EMBED_BATCH]
            encoded = self._tokenizer.encode_batch(batch)

            ids = np.array([e.ids for e in encoded], dtype=np.int64)
            mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
            feed = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self._inputs:
                feed["token_type_ids"] = np.zeros_like(ids)
            feed = {k: v for k, v in feed.items() if k in self._inputs}

            hidden = self._session.run(None, feed)[0]
            expanded = mask[..., None].astype(hidden.dtype)
            summed = (hidden * expanded).sum(axis=1)
            counts = np.clip(expanded.sum(axis=1), 1e-9, None)
            pooled = summed / counts
            norms = np.clip(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12, None)
            out.extend((pooled / norms).astype("float32").tolist())
        return out

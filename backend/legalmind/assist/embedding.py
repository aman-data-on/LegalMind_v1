"""The embedding-model contract — `AM-26` r1–r5.

No model is named here, and none is imported. `AM-26` r2 requires selection **by
measurement**, smallest-that-passes, and r1 requires that *"the model identity is
configuration, and no other code knows which model is running"*. So this module fixes
the interface a candidate must satisfy and nothing else; the selection lives in
`tools/benchmark_retrieval.py`'s results and in the decision record.

Writing an implementation here before a model is selected would settle by import what
`AM-26` r2 says to settle by measurement — and pinning a dimension in the schema first
is the same mistake in DDL, which is why `chunk_embeddings` does not exist yet.

--------------------------------------------------------------------------
What a candidate has to satisfy to be admissible at all
--------------------------------------------------------------------------
Locked, not preference:

    self-hosted, open-weight     `AM-26` ADDED row, and `AM-30` t1 keeps embedding
                                 input off any hosted API — so the highest-volume,
                                 most mechanical step never leaves the building
    no outbound network route    `AM-26` — the local inference runtime has none
    weights fetched once,        `AM-26` r5 — never fetched at runtime, so a model
    checksummed, stored local    that resolves from a hub on first use is not eligible
    version pinned and recorded  `AM-26` r4 — against every answer
    no fine-tuning, no training  `AM-26` NOT-ADDED

`dimensions` is read from the model, never chosen: it is a property of the weights, and
the schema follows it rather than the other way round.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingBackend(Protocol):
    """One embedding model, behind `AM-26` r1's single interface."""

    @property
    def identity(self) -> str:
        """Stable `name@version` recorded against every answer (`AM-26` r4).

        A floating alias is not a pin — the same discipline `AM-30` t7 applies to the
        generative model.
        """
        ...

    @property
    def dimensions(self) -> int:
        """The vector width, read from the model. Never configured, never assumed."""
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch. Deterministic for a fixed model version.

        Determinism here is not `ENG-11` — `AM-28` r1 bars the assist lane from that
        gate — but re-embedding a corpus must not move vectors, or a stored embedding
        and a fresh query embedding would no longer be comparable.
        """
        ...


@runtime_checkable
class RetrievalStrategy(Protocol):
    """A way of ranking chunks for a query, so strategies can be compared like for like.

    Implemented by the lexical search that exists today, and by the vector and hybrid
    strategies a selected model unlocks. The benchmark measures whatever satisfies this,
    which is what makes "smallest that passes" a comparison rather than an assertion.
    """

    @property
    def label(self) -> str:
        ...

    def rank(self, db, *, document_version_id, query: str,
             limit: int) -> list[tuple[object, float]]:
        """Return (chunk_id, score) best-first.

        `document_version_id` is the authorized scope and must be applied **inside**
        the query, per `AM-25` r6 — a strategy that ranks first and filters afterwards
        is not admissible here, whatever its scores look like.
        """
        ...


class LexicalStrategy:
    """The strategy that exists today: `tsvector` + trigram, ordered by `ts_rank`.

    The measurement baseline. A candidate embedding model has to beat this on the
    categories it is supposed to help with, or it is not earning its runtime — which is
    the concrete form of `AM-26` r2's "the smallest model meeting the quality bar wins".
    """

    label = "lexical (tsvector + trigram)"

    def rank(self, db, *, document_version_id, query: str,
             limit: int) -> list[tuple[object, float]]:
        from legalmind.assist import store

        hits = store.search_chunks(db, document_version_id=document_version_id,
                                   query=query, limit=limit)
        return [(h.chunk_id, h.retrieval_score) for h in hits]

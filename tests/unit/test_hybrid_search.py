"""Unit tests for HybridSearch weighted RRF behavior."""

from __future__ import annotations

from unittest.mock import Mock

from src.core.query_engine.hybrid_search import HybridSearch, HybridSearchConfig
from src.core.types import RetrievalResult


def test_hybrid_search_uses_weighted_rrf_when_configured() -> None:
    """HybridSearch should call fuse_with_weights when weights are non-default."""
    fusion = Mock()
    fusion.fuse.return_value = []
    fusion.fuse_with_weights.return_value = []

    config = HybridSearchConfig()
    config.rrf_weights = {"dense": 1.2, "sparse": 0.8}  # type: ignore[attr-defined]
    search = HybridSearch(
        settings=None,
        query_processor=None,
        dense_retriever=None,
        sparse_retriever=None,
        fusion=fusion,
        config=config,
    )

    dense_results = [
        RetrievalResult(chunk_id="d1", score=0.9, text="dense", metadata={})
    ]
    sparse_results = [
        RetrievalResult(chunk_id="s1", score=0.8, text="sparse", metadata={})
    ]

    search._fuse_results(dense_results, sparse_results, top_k=5, trace=None)
    fusion.fuse_with_weights.assert_called_once()


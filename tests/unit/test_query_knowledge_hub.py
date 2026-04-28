"""Unit tests for query_knowledge_hub tool enhancements."""

from __future__ import annotations

from src.core.types import RetrievalResult
from src.mcp_server.tools.query_knowledge_hub import (
    QueryKnowledgeHubConfig,
    QueryKnowledgeHubTool,
)


def test_build_feedback_event_contains_core_fields() -> None:
    """Feedback payload should include query, collection and top results."""
    tool = QueryKnowledgeHubTool()
    results = [
        RetrievalResult(
            chunk_id="chunk-1",
            score=0.91,
            text="RRF is rank fusion.",
            metadata={"source_path": "docs/rrf.md"},
        )
    ]

    payload = tool._build_feedback_event(  # type: ignore[attr-defined]
        query="什么是RRF",
        collection="knowledge_hub",
        top_k=5,
        results=results,
    )

    assert payload["query"] == "什么是RRF"
    assert payload["collection"] == "knowledge_hub"
    assert payload["top_k"] == 5
    assert payload["result_count"] == 1
    assert payload["final_chunk_ids"] == ["chunk-1"]


def test_doc_aggregation_uses_configurable_tail_decay() -> None:
    """Document aggregation should use configurable tail decay."""
    tool = QueryKnowledgeHubTool(
        config=QueryKnowledgeHubConfig(
            enable_doc_aggregation=True,
            doc_aggregation_tail_decay=1.0,
        )
    )
    results = [
        RetrievalResult(
            chunk_id="a1",
            score=0.8,
            text="A1",
            metadata={"source_path": "docA.md"},
        ),
        RetrievalResult(
            chunk_id="a2",
            score=0.6,
            text="A2",
            metadata={"source_path": "docA.md"},
        ),
    ]
    merged = tool._aggregate_results_by_document(results, top_k=5)
    assert len(merged) == 1
    # expected = best + tail*(decay/index)=0.8 + 0.6*(1.0/2)=1.1
    assert abs(merged[0].score - 1.1) < 1e-9


def test_query_tool_applies_runtime_config_from_settings() -> None:
    """Tool should sync doc aggregation and feedback loop config from settings."""
    class _Retrieval:
        doc_aggregation = {"enabled": False, "tail_decay": 0.7}
        feedback_loop = {"enabled": False, "log_path": "./logs/custom_feedback.jsonl"}

    class _VectorStore:
        collection_name = "knowledge_hub"

    class _Settings:
        retrieval = _Retrieval()
        vector_store = _VectorStore()

    tool = QueryKnowledgeHubTool(settings=_Settings())
    _ = tool.settings

    assert tool.config.enable_doc_aggregation is False
    assert abs(tool.config.doc_aggregation_tail_decay - 0.7) < 1e-9
    assert tool._qa_feedback_logger.enabled is False  # type: ignore[attr-defined]


def test_query_tool_persists_qa_event_and_extracts_candidates() -> None:
    class _Store:
        def __init__(self) -> None:
            self.saved = False
            self.last_citations = []

        def insert_event(self, query, collection, answer, citations):  # type: ignore[no-untyped-def]
            self.saved = True
            self.last_citations = citations
            return "event-1"

    class _Extractor:
        def __init__(self) -> None:
            self.called = False

        def extract(self, query, answer, citations):  # type: ignore[no-untyped-def]
            self.called = True
            return [{"statement": "RRF 是融合排序", "confidence": 0.9}]

    class _VectorStore:
        collection_name = "knowledge_hub"

    class _Settings:
        vector_store = _VectorStore()
        wiki_builder = {"enabled": True}

    store = _Store()
    extractor = _Extractor()
    tool = QueryKnowledgeHubTool(settings=_Settings())
    _ = tool.settings
    results = [
        RetrievalResult(
            chunk_id="chunk-1",
            score=0.9,
            text="RRF",
            metadata={},
        )
    ]
    response = tool._response_builder.build(  # type: ignore[attr-defined]
        results=results,
        query="什么是RRF",
        collection="knowledge_hub",
    )

    tool._persist_qa_knowledge(  # type: ignore[attr-defined]
        query="什么是RRF",
        collection="knowledge_hub",
        response=response,
        results=results,
        qa_event_store=store,
        candidate_extractor=extractor,
    )

    assert store.saved is True
    assert store.last_citations == ["chunk-1"]
    assert extractor.called is True


def test_query_tool_persist_qa_knowledge_is_non_blocking() -> None:
    class _FailStore:
        def insert_event(self, query, collection, answer, citations):  # type: ignore[no-untyped-def]
            raise RuntimeError("db unavailable")

    class _Extractor:
        def extract(self, query, answer, citations):  # type: ignore[no-untyped-def]
            return []

    tool = QueryKnowledgeHubTool()
    results = [RetrievalResult(chunk_id="chunk-1", score=0.9, text="RRF", metadata={})]
    response = tool._response_builder.build(  # type: ignore[attr-defined]
        results=results,
        query="什么是RRF",
        collection="knowledge_hub",
    )

    # side-effect failures should not break query main flow
    tool._persist_qa_knowledge(  # type: ignore[attr-defined]
        query="什么是RRF",
        collection="knowledge_hub",
        response=response,
        results=results,
        qa_event_store=_FailStore(),
        candidate_extractor=_Extractor(),
    )


def test_query_tool_skips_qa_persist_when_wiki_builder_disabled() -> None:
    class _Store:
        def __init__(self) -> None:
            self.called = False

        def insert_event(self, query, collection, answer, citations):  # type: ignore[no-untyped-def]
            self.called = True
            return "event-1"

    class _Extractor:
        def extract(self, query, answer, citations):  # type: ignore[no-untyped-def]
            return []

    class _VectorStore:
        collection_name = "knowledge_hub"

    class _Settings:
        vector_store = _VectorStore()
        wiki_builder = {"enabled": False}

    store = _Store()
    tool = QueryKnowledgeHubTool(settings=_Settings())
    _ = tool.settings
    results = [RetrievalResult(chunk_id="chunk-1", score=0.9, text="RRF", metadata={})]
    response = tool._response_builder.build(  # type: ignore[attr-defined]
        results=results,
        query="什么是RRF",
        collection="knowledge_hub",
    )

    tool._persist_qa_knowledge(  # type: ignore[attr-defined]
        query="什么是RRF",
        collection="knowledge_hub",
        response=response,
        results=results,
        qa_event_store=store,
        candidate_extractor=_Extractor(),
    )

    assert store.called is False


"""Unit tests for QA event store."""

from __future__ import annotations

from src.knowledge.qa_event_store import QAEventStore


def test_qa_event_store_insert_and_list(tmp_path) -> None:
    db_path = tmp_path / "qa_events.db"
    store = QAEventStore(str(db_path))
    event_id = store.insert_event(
        query="什么是RRF",
        collection="knowledge_hub",
        answer="RRF 是一种融合排序方法",
        citations=["chunk-1", "chunk-2"],
    )

    rows = store.list_recent(limit=10)
    assert len(rows) == 1
    assert rows[0]["id"] == event_id
    assert rows[0]["query"] == "什么是RRF"

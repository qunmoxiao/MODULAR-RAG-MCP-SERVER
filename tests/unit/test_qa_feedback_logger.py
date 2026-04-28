"""Unit tests for QA feedback loop logger."""

from __future__ import annotations

from pathlib import Path

from src.observability.qa_feedback_logger import QAFeedbackLogger


def test_qa_feedback_logger_writes_jsonl(tmp_path: Path) -> None:
    """Logger should append one JSONL record per event."""
    log_path = tmp_path / "qa_feedback.jsonl"
    logger = QAFeedbackLogger(log_path=str(log_path))

    logger.log_event(
        {
            "query": "什么是RRF",
            "collection": "knowledge_hub",
            "result_count": 3,
            "follow_up": False,
        }
    )

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert '"query": "什么是RRF"' in lines[0]


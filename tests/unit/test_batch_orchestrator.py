"""Tests for wiki batch window orchestration."""

from __future__ import annotations

from src.knowledge.batch_orchestrator import WikiBatchOrchestrator


def test_batch_orchestrator_reports_window_minutes() -> None:
    orchestrator = WikiBatchOrchestrator(batch_window_minutes=15)
    assert orchestrator.window_seconds == 900

"""Batch orchestration metadata for wiki builder."""

from __future__ import annotations


class WikiBatchOrchestrator:
    """Represents batch window settings for periodic processing."""

    def __init__(self, batch_window_minutes: int) -> None:
        self.batch_window_minutes = batch_window_minutes

    @property
    def window_seconds(self) -> int:
        return self.batch_window_minutes * 60

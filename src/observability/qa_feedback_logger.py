"""QA feedback loop logger for query-answer traces."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from src.core.settings import resolve_path


class QAFeedbackLogger:
    """Append query-answer events as JSONL records."""

    def __init__(
        self,
        log_path: str = "logs/qa_feedback.jsonl",
        enabled: bool = True,
    ) -> None:
        self.enabled = enabled
        self.log_path = resolve_path(log_path)
        Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)

    def log_event(self, payload: Dict[str, Any]) -> None:
        """Write one event line with UTC timestamp."""
        if not self.enabled:
            return

        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        with Path(self.log_path).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")


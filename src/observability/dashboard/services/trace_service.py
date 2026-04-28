"""TraceService – read and parse traces from logs/traces.jsonl.

Provides a typed, filterable interface over the raw JSONL trace log.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.settings import resolve_path

logger = logging.getLogger(__name__)

# Default path to the traces file (absolute, CWD-independent)
DEFAULT_TRACES_PATH = resolve_path("logs/traces.jsonl")


class TraceService:
    """Read-only service for querying recorded traces.

    Args:
        traces_path: Path to the JSONL file.  Defaults to
            ``logs/traces.jsonl``.
    """

    def __init__(self, traces_path: Optional[str | Path] = None) -> None:
        self.traces_path = Path(traces_path) if traces_path else DEFAULT_TRACES_PATH

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_traces(
        self,
        trace_type: Optional[str] = None,
        limit: int = 0,
    ) -> List[Dict[str, Any]]:
        """Return traces in reverse-chronological order.

        Args:
            trace_type: Filter by ``trace_type`` field (e.g.
                ``"ingestion"`` or ``"query"``).  ``None`` = all.
            limit: Maximum number of traces to return.

        Returns:
            List of trace dicts (newest first).
        """
        traces = self._load_all()

        if trace_type:
            traces = [t for t in traces if t.get("trace_type") == trace_type]

        # Newest first
        traces.sort(key=lambda t: t.get("started_at", ""), reverse=True)

        return traces[:limit] if limit > 0 else traces

    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single trace by its ``trace_id``.

        Returns:
            Trace dict, or ``None`` if not found.
        """
        for t in self._load_all():
            if t.get("trace_id") == trace_id:
                return t
        return None

    def get_stage_timings(self, trace: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract stage timings from a trace.

        Returns:
            List of dicts with keys: stage_name, elapsed_ms, data.
            Ordered by appearance.
        """
        stages = trace.get("stages", [])
        timings: List[Dict[str, Any]] = []
        for s in stages:
            # The raw stage dict has: stage, timestamp, data (dict), elapsed_ms
            # Extract the inner 'data' dict directly rather than flattening
            stage_data = s.get("data", {})
            if not isinstance(stage_data, dict):
                stage_data = {}
            # Backward compatibility: older traces store stage fields at top level
            # (e.g., {"stage":"load","method":"pdf"}) instead of nested data.
            if "method" in s and "method" not in stage_data:
                stage_data = {**stage_data, "method": s.get("method")}
            timings.append(
                {
                    "stage_name": s.get("stage"),
                    "elapsed_ms": s.get("elapsed_ms", 0),
                    "data": stage_data,
                }
            )
        return timings

    def list_sessions(
        self,
        trace_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Group traces into sessions and return summary for each.

        Traces with ``session_id`` are grouped by that field.  Legacy traces
        (without ``session_id``) are clustered into 5-minute time windows.

        Args:
            trace_type: Filter by trace_type before grouping.

        Returns:
            List of session dicts sorted newest-first.  Each dict contains:
            ``session_id``, ``started_at``, ``file_count``, ``success_count``,
            ``fail_count``, ``total_chunks``, ``total_images``, ``traces``.
        """
        traces = self.list_traces(trace_type=trace_type)

        # Partition: traces with session_id vs legacy
        sessions_map: Dict[str, List[Dict[str, Any]]] = {}
        legacy_traces: List[Dict[str, Any]] = []

        for t in traces:
            sid = t.get("session_id")
            if sid:
                sessions_map.setdefault(sid, []).append(t)
            else:
                legacy_traces.append(t)

        # Cluster legacy traces by 5-minute windows
        if legacy_traces:
            legacy_traces.sort(key=lambda t: t.get("started_at", ""))
            window_minutes = 5
            current_bucket: List[Dict[str, Any]] = []
            bucket_start: Optional[datetime] = None

            for t in legacy_traces:
                ts_str = t.get("started_at", "")
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    ts = None

                if ts is None:
                    # Unparseable timestamp → own bucket
                    key = f"legacy-{t.get('trace_id', 'unknown')[:12]}"
                    sessions_map.setdefault(key, []).append(t)
                    continue

                if bucket_start is None or (ts - bucket_start) > timedelta(minutes=window_minutes):
                    # Start new bucket
                    if current_bucket:
                        bkey = f"legacy-{bucket_start.strftime('%Y%m%d%H%M')}"
                        sessions_map.setdefault(bkey, []).extend(current_bucket)
                    current_bucket = [t]
                    bucket_start = ts
                else:
                    current_bucket.append(t)

            if current_bucket and bucket_start is not None:
                bkey = f"legacy-{bucket_start.strftime('%Y%m%d%H%M')}"
                sessions_map.setdefault(bkey, []).extend(current_bucket)

        # Build session summaries
        sessions: List[Dict[str, Any]] = []
        for sid, group in sessions_map.items():
            started_at = min(t.get("started_at", "") for t in group)
            file_count = len(group)

            success_count = 0
            fail_count = 0
            total_chunks = 0
            total_images = 0

            for t in group:
                stages = {s.get("stage"): s.get("data", {}) for s in t.get("stages", [])}
                has_upsert = "upsert" in stages
                success_count += 1 if has_upsert else 0
                fail_count += 0 if has_upsert else 1

                split_d = stages.get("split", {})
                total_chunks += split_d.get("chunk_count", 0)

                load_d = stages.get("load", {})
                total_images += load_d.get("image_count", 0)

            sessions.append({
                "session_id": sid,
                "started_at": started_at,
                "file_count": file_count,
                "success_count": success_count,
                "fail_count": fail_count,
                "total_chunks": total_chunks,
                "total_images": total_images,
                "traces": sorted(group, key=lambda t: t.get("started_at", "")),
            })

        sessions.sort(key=lambda s: s["started_at"], reverse=True)
        return sessions

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_all(self) -> List[Dict[str, Any]]:
        """Parse every line in the JSONL file.

        Silently skips malformed lines.
        """
        if not self.traces_path.exists():
            return []

        traces: List[Dict[str, Any]] = []
        with self.traces_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    traces.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.debug("Skipping malformed trace line: %s", line[:80])
        return traces

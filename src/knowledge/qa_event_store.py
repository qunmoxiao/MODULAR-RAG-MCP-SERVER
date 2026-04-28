"""SQLite storage for QA events."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


class QAEventStore:
    """Persist QA events for downstream wiki building."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS qa_events (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    query TEXT NOT NULL,
                    collection_name TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    citations_json TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def insert_event(
        self,
        query: str,
        collection: str,
        answer: str,
        citations: List[str],
    ) -> str:
        event_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        citations_json = json.dumps(citations, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO qa_events (
                    id, created_at, query, collection_name, answer, citations_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (event_id, created_at, query, collection, answer, citations_json),
            )
            conn.commit()
        return event_id

    def list_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, query, collection_name, answer, citations_json
                FROM qa_events
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "created_at": row[1],
                "query": row[2],
                "collection": row[3],
                "answer": row[4],
                "citations": json.loads(row[5]),
            }
            for row in rows
        ]

"""MCP resources/prompts registry for prompt file discovery."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, List
import logging

from mcp import types

from src.core.settings import load_settings, resolve_path

logger = logging.getLogger(__name__)


class ResourcePromptRegistry:
    """Expose prompt templates as MCP resources and prompts."""

    def __init__(self, prompts_dir: str = "config/prompts") -> None:
        self.prompts_dir = resolve_path(prompts_dir)
        self._wiki_events_db = resolve_path("data/db/wiki/qa_events.db")

    def _prompt_files(self) -> List[Path]:
        if not self.prompts_dir.exists():
            return []
        return sorted(self.prompts_dir.glob("*.txt"))

    def _resource_uri(self, prompt_name: str) -> str:
        return f"mrag://prompts/{prompt_name}"

    def _validate_prompt_name(self, name: str) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise ValueError(f"Invalid prompt name: {name}")

    def list_resources(self) -> List[types.Resource]:
        resources: List[types.Resource] = []
        resources.append(
            types.Resource(
                name="system:wiki_builder_status",
                uri="mrag://system/wiki_builder_status",
                description="Runtime status of QA->Wiki builder switch and event stats",
                mimeType="application/json",
            )
        )
        for file_path in self._prompt_files():
            prompt_name = file_path.stem
            resources.append(
                types.Resource(
                    name=f"prompt:{prompt_name}",
                    uri=self._resource_uri(prompt_name),
                    description=f"Prompt template for {prompt_name}",
                    mimeType="text/plain",
                )
            )
        return resources

    def read_resource(self, uri: str) -> types.ReadResourceResult:
        if uri == "mrag://system/wiki_builder_status":
            payload = self._build_wiki_builder_status()
            return types.ReadResourceResult(
                contents=[
                    types.TextResourceContents(
                        uri=uri,
                        mimeType="application/json",
                        text=json.dumps(payload, ensure_ascii=False, indent=2),
                    )
                ]
            )
        prompt_name = uri.rstrip("/").split("/")[-1]
        self._validate_prompt_name(prompt_name)
        target = self.prompts_dir / f"{prompt_name}.txt"
        if not target.exists():
            raise ValueError(f"Prompt resource not found: {uri}")

        content = target.read_text(encoding="utf-8")
        return types.ReadResourceResult(
            contents=[
                types.TextResourceContents(
                    uri=uri,
                    mimeType="text/plain",
                    text=content,
                )
            ]
        )

    def list_prompts(self) -> List[types.Prompt]:
        return [
            types.Prompt(
                name="retrieval_answer",
                description="Generate answer draft from retrieved context",
                arguments=[
                    types.PromptArgument(
                        name="query",
                        description="User query",
                        required=True,
                    )
                ],
            ),
            types.Prompt(
                name="document_summary",
                description="Generate concise summary for one document",
                arguments=[
                    types.PromptArgument(
                        name="doc_id",
                        description="Document identifier",
                        required=True,
                    )
                ],
            ),
        ]

    def get_prompt(self, name: str, arguments: Dict[str, Any]) -> types.GetPromptResult:
        self._validate_prompt_name(name)
        template_file = self.prompts_dir / f"{name}.txt"
        if template_file.exists():
            template = template_file.read_text(encoding="utf-8")
        else:
            if name == "retrieval_answer":
                template = "Use context to answer query: {query}"
            elif name == "document_summary":
                template = "Summarize document: {doc_id}"
            else:
                raise ValueError(f"Prompt not found: {name}")

        rendered = template.format(**arguments)
        return types.GetPromptResult(
            description=f"Prompt for {name}",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(type="text", text=rendered),
                )
            ],
        )

    def _build_wiki_builder_status(self) -> Dict[str, Any]:
        wiki_cfg: Dict[str, Any] = {}
        settings_error: str | None = None
        try:
            settings = load_settings()
            wiki_cfg = getattr(settings, "wiki_builder", {}) or {}
        except Exception as exc:
            settings_error = str(exc)
            logger.warning("Failed to load settings for wiki status: %s", exc)

        event_count = 0
        latest_created_at = None

        if self._wiki_events_db.exists():
            try:
                with sqlite3.connect(str(self._wiki_events_db)) as conn:
                    cursor = conn.execute("SELECT COUNT(1) FROM qa_events")
                    row = cursor.fetchone()
                    event_count = int(row[0]) if row else 0
                    latest = conn.execute(
                        "SELECT created_at FROM qa_events ORDER BY created_at DESC LIMIT 1"
                    ).fetchone()
                    latest_created_at = latest[0] if latest else None
            except sqlite3.OperationalError as exc:
                logger.warning("Wiki events table unavailable, fallback to empty stats: %s", exc)
                event_count = 0
                latest_created_at = None

        payload: Dict[str, Any] = {
            "wiki_builder": {
                "enabled": bool(wiki_cfg.get("enabled", False)),
                "batch_window_minutes": int(wiki_cfg.get("batch_window_minutes", 15)),
                "promote_threshold": float(wiki_cfg.get("promote_threshold", 0.8)),
                "candidate_threshold": float(wiki_cfg.get("candidate_threshold", 0.55)),
                "dual_write_markdown": bool(wiki_cfg.get("dual_write_markdown", True)),
            },
            "qa_event_store": {
                "path": str(self._wiki_events_db),
                "event_count": event_count,
                "latest_created_at": latest_created_at,
            },
        }
        if settings_error:
            payload["settings_error"] = settings_error
        return payload


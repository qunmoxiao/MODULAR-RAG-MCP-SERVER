"""Unit tests for MCP resources/prompts registry."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from src.mcp_server.resource_prompt_registry import ResourcePromptRegistry


def test_registry_lists_prompt_resources(tmp_path: Path) -> None:
    """Registry should expose prompt files as MCP resources."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "retrieval_answer.txt").write_text(
        "Answer query: {query}", encoding="utf-8"
    )

    registry = ResourcePromptRegistry(prompts_dir=str(prompts_dir))
    resources = registry.list_resources()

    assert any("mrag://prompts/retrieval_answer" in str(r.uri) for r in resources)


def test_registry_get_prompt_template(tmp_path: Path) -> None:
    """Registry should resolve prompt templates with arguments."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "retrieval_answer.txt").write_text(
        "Answer query: {query}", encoding="utf-8"
    )

    registry = ResourcePromptRegistry(prompts_dir=str(prompts_dir))
    result = registry.get_prompt("retrieval_answer", {"query": "什么是RRF"})

    assert len(result.messages) > 0
    assert "什么是RRF" in result.messages[0].content.text


def test_registry_rejects_path_traversal_prompt_name(tmp_path: Path) -> None:
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    registry = ResourcePromptRegistry(prompts_dir=str(prompts_dir))

    try:
        registry.get_prompt("../secret", {})
        assert False, "Expected ValueError for invalid prompt name"
    except ValueError as exc:
        assert "Invalid prompt name" in str(exc)


def test_registry_exposes_wiki_builder_status_resource(tmp_path: Path) -> None:
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    registry = ResourcePromptRegistry(prompts_dir=str(prompts_dir))

    resources = registry.list_resources()
    uris = [str(r.uri) for r in resources]
    assert "mrag://system/wiki_builder_status" in uris


def test_registry_reads_wiki_builder_status_resource(tmp_path: Path) -> None:
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    registry = ResourcePromptRegistry(prompts_dir=str(prompts_dir))

    result = registry.read_resource("mrag://system/wiki_builder_status")
    assert len(result.contents) == 1
    assert "wiki_builder" in result.contents[0].text


def test_registry_wiki_status_degrades_when_table_missing(tmp_path: Path) -> None:
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "qa_events.db"
    sqlite3.connect(str(db_path)).close()  # create empty sqlite without qa_events table

    registry = ResourcePromptRegistry(prompts_dir=str(prompts_dir))
    registry._wiki_events_db = db_path  # type: ignore[attr-defined]

    result = registry.read_resource("mrag://system/wiki_builder_status")
    assert len(result.contents) == 1
    assert '"event_count": 0' in result.contents[0].text


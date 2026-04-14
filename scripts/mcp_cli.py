#!/usr/bin/env python
"""CLI wrapper for core MCP tools in Modular RAG MCP Server.

This script provides a direct command-line interface for the same capabilities
already exposed via MCP tools:
- query_knowledge_hub
- list_collections
- get_document_summary

Usage examples:
    python scripts/mcp_cli.py query --query "什么是 RAG" --top-k 5 --collection default
    python scripts/mcp_cli.py list-collections --include-stats
    python scripts/mcp_cli.py get-document-summary --doc-id doc_abc123 --collection default
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.settings import load_settings
from src.mcp_server.tools.get_document_summary import GetDocumentSummaryTool
from src.mcp_server.tools.list_collections import ListCollectionsTool
from src.mcp_server.tools.query_knowledge_hub import QueryKnowledgeHubTool


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CLI wrapper for Modular RAG MCP tools.",
    )
    parser.add_argument(
        "--config",
        default=str(PROJECT_ROOT / "config" / "settings.yaml"),
        help="Path to settings YAML (default: config/settings.yaml).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON when available.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    query_parser = subparsers.add_parser(
        "query",
        help="Run query_knowledge_hub from CLI.",
    )
    query_parser.add_argument("--query", required=True, help="Search query text.")
    query_parser.add_argument("--top-k", type=int, default=5, help="Max results to return.")
    query_parser.add_argument("--collection", default=None, help="Optional collection name.")

    list_parser = subparsers.add_parser(
        "list-collections",
        help="Run list_collections from CLI.",
    )
    list_parser.add_argument(
        "--include-stats",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include collection document counts (default: true).",
    )

    summary_parser = subparsers.add_parser(
        "get-document-summary",
        help="Run get_document_summary from CLI.",
    )
    summary_parser.add_argument("--doc-id", required=True, help="Document ID.")
    summary_parser.add_argument("--collection", default=None, help="Optional collection name.")

    return parser


async def _run_query(args: argparse.Namespace, settings_path: str) -> int:
    settings = load_settings(settings_path)
    tool = QueryKnowledgeHubTool(settings=settings)
    response = await tool.execute(
        query=args.query,
        top_k=args.top_k,
        collection=args.collection,
    )

    if args.json:
        print(
            json.dumps(
                {
                    "content": response.content,
                    "citations": [citation.to_dict() for citation in response.citations],
                    "metadata": response.metadata,
                    "is_empty": response.is_empty,
                    "has_images": response.has_images,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(response.content)

    return 1 if (response.is_empty and "error" in response.metadata) else 0


async def _run_list_collections(args: argparse.Namespace, settings_path: str) -> int:
    settings = load_settings(settings_path)
    tool = ListCollectionsTool(settings=settings)
    collections = await asyncio.to_thread(
        tool.list_collections,
        args.include_stats,
    )

    if args.json:
        print(
            json.dumps(
                [item.to_dict() for item in collections],
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(tool.format_response(collections))

    return 0


async def _run_get_document_summary(args: argparse.Namespace, settings_path: str) -> int:
    settings = load_settings(settings_path)
    tool = GetDocumentSummaryTool(settings=settings)

    try:
        summary = await asyncio.to_thread(
            tool.get_document_summary,
            args.doc_id,
            args.collection,
        )
    except Exception as exc:
        if args.json:
            print(
                json.dumps(
                    {"error": str(exc)},
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(tool.format_error(exc))
        return 1

    if args.json:
        print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(tool.format_response(summary))

    return 0


async def _amain() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    settings_path = str(Path(args.config).resolve())
    command = args.command

    if command == "query":
        return await _run_query(args, settings_path)
    if command == "list-collections":
        return await _run_list_collections(args, settings_path)
    if command == "get-document-summary":
        return await _run_get_document_summary(args, settings_path)

    parser.error(f"Unsupported command: {command}")
    return 2


def main() -> int:
    try:
        return asyncio.run(_amain())
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 130
    except Exception as exc:
        print(f"CLI error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

"""
Modular RAG MCP Server - Main Entry Point

This is the entry point for the MCP Server. It starts the MCP server
using stdio transport for communication with MCP clients.
"""

from __future__ import annotations

import sys

from src.mcp_server.server import main as mcp_main


def _dispatch_to_cli() -> int:
    """Dispatch to CLI entrypoint while removing the `cli` token from argv."""
    from scripts.mcp_cli import main as cli_main

    # `python main.py cli --query ...` -> pass `--query ...` to CLI parser
    sys.argv = [sys.argv[0], *sys.argv[2:]]
    return cli_main()


def main() -> int:
    """Unified entrypoint: MCP server by default, CLI when requested.

    - MCP mode (default): python main.py
    - CLI mode:           python main.py cli <subcommand> [args...]
    """
    if len(sys.argv) > 1 and sys.argv[1] == "cli":
        return _dispatch_to_cli()
    return mcp_main()

if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python
"""Test MCP Server tools via stdio."""

import subprocess
import json
import sys

def send_request(proc, request):
    """Send a JSON-RPC request and get response."""
    proc.stdin.write(json.dumps(request) + "\n")
    proc.stdin.flush()
    response = proc.stdout.readline()
    return json.loads(response)

def main():
    # Start MCP server
    proc = subprocess.Popen(
        [sys.executable, "main.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    try:
        # 1. Initialize
        print("🔄 Initializing MCP Server...")
        init_request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "test-client", "version": "1.0"},
                "capabilities": {}
            },
            "id": 1
        }
        response = send_request(proc, init_request)
        print(f"✅ Initialized: {response.get('result', {}).get('serverInfo', {})}")

        # 2. List tools
        print("\n📋 Listing available tools...")
        list_tools = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": 2
        }
        response = send_request(proc, list_tools)
        tools = response.get("result", {}).get("tools", [])
        for tool in tools:
            print(f"   - {tool['name']}: {tool.get('description', '')[:50]}...")

        # 3. Call list_collections
        print("\n📚 Calling list_collections...")
        call_tool = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "list_collections",
                "arguments": {}
            },
            "id": 3
        }
        response = send_request(proc, call_tool)
        result = response.get("result", {})
        if "content" in result:
            for content in result["content"]:
                if content.get("type") == "text":
                    print(f"   {content['text']}")

        # 4. Query knowledge hub
        print("\n🔍 Querying knowledge hub...")
        query_tool = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "query_knowledge_hub",
                "arguments": {
                    "query": "这个文档是什么内容",
                    "collection": "demo",
                    "top_k": 3
                }
            },
            "id": 4
        }
        response = send_request(proc, query_tool)
        result = response.get("result", {})
        if "content" in result:
            for content in result["content"]:
                if content.get("type") == "text":
                    print(f"   {content['text'][:500]}...")

        print("\n✅ Test completed successfully!")

    except Exception as e:
        print(f"❌ Error: {e}")
        stderr = proc.stderr.read()
        if stderr:
            print(f"Server stderr: {stderr}")
    finally:
        proc.terminate()

if __name__ == "__main__":
    main()

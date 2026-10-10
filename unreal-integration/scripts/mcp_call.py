#!/usr/bin/env python3
"""Minimal CLI client for the official Unreal MCP server (HTTP transport).

  python3 scripts/mcp_call.py tools/list
  python3 scripts/mcp_call.py list_toolsets
  python3 scripts/mcp_call.py describe_toolset '{"toolset": "..."}'
  python3 scripts/mcp_call.py call_tool '{"tool": "...", "arguments": {...}}'

Any name other than tools/list is sent as tools/call with the JSON arguments.
Stdlib only; endpoint from $UNREAL_MCP_URL (default http://127.0.0.1:8000/mcp).
"""
import json
import os
import sys
import urllib.request

URL = os.environ.get("UNREAL_MCP_URL", "http://127.0.0.1:8000/mcp")
HDRS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


def post(payload, session=None):
    h = dict(HDRS)
    if session:
        h["Mcp-Session-Id"] = session
    req = urllib.request.Request(URL, json.dumps(payload).encode(), h)
    with urllib.request.urlopen(req, timeout=float(os.environ.get("MCP_TIMEOUT", "120"))) as r:
        body = r.read().decode()
        sid = r.headers.get("Mcp-Session-Id")
    if body.startswith("event:") or body.startswith("data:"):  # SSE framing
        body = "\n".join(l[5:].strip() for l in body.splitlines() if l.startswith("data:"))
    return (json.loads(body) if body.strip() else None), sid


def main():
    _, sid = post({"jsonrpc": "2.0", "id": 0, "method": "initialize",
                   "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                              "clientInfo": {"name": "mcp_call", "version": "0"}}})
    post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
    name = sys.argv[1] if len(sys.argv) > 1 else "tools/list"
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    if name == "tools/list":
        msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    else:
        msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}}
    res, _ = post(msg, sid)
    result = (res or {}).get("result", res)
    for c in (result or {}).get("content", []) if isinstance(result, dict) else []:
        if c.get("type") == "text":
            try:
                print(json.dumps(json.loads(c["text"]), indent=2))
            except (ValueError, TypeError):
                print(c["text"])
            return
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

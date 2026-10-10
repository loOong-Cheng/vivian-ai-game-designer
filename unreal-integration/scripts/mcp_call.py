#!/usr/bin/env python3
"""Minimal CLI client for the official Unreal MCP server (HTTP transport).

  python3 scripts/mcp_call.py tools/list
  python3 scripts/mcp_call.py list_toolsets
  python3 scripts/mcp_call.py describe_toolset '{"toolset_name": "..."}'
  python3 scripts/mcp_call.py call_tool '{"toolset_name": "...", "tool_name": "...", "arguments": {...}}'
  python scripts/mcp_call.py call_tool @args.json        # JSON from a file
  '{"tool_name": "..."}' | python scripts/mcp_call.py call_tool -   # JSON from stdin

Windows PowerShell 5.1 strips the double quotes from JSON passed as a native-exe argument,
so on Windows use @file or stdin (a UTF-8 BOM is ignored in both).

Any name other than tools/list is sent as tools/call with the JSON arguments.
Base64 images in the result (e.g. CaptureViewport) are saved as files under $MCP_IMAGE_DIR
(default <temp>/unreal_mcp) and replaced by their path.
Stdlib only; endpoint from $UNREAL_MCP_URL (default http://127.0.0.1:8000/mcp).
"""
import base64
import hashlib
import json
import os
import sys
import tempfile
import time
import urllib.request

URL = os.environ.get("UNREAL_MCP_URL", "http://127.0.0.1:8000/mcp")
HDRS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
IMAGE_DIR = os.environ.get("MCP_IMAGE_DIR", os.path.join(tempfile.gettempdir(), "unreal_mcp"))
_saved = {}


def save_images(obj):
    """Replace every {"mimeType": "image/...", "data": <base64>} payload with the path of a saved file."""
    if isinstance(obj, list):
        return [save_images(v) for v in obj]
    if not isinstance(obj, dict):
        return obj
    if str(obj.get("mimeType", "")).startswith("image/") and isinstance(obj.get("data"), str) and obj["data"]:
        key = hashlib.sha1(obj["data"].encode()).hexdigest()
        if key not in _saved:
            os.makedirs(IMAGE_DIR, exist_ok=True)
            ext = obj["mimeType"].split("/")[1].split("+")[0]
            _saved[key] = os.path.join(IMAGE_DIR, f"{time.strftime('%H%M%S')}_{key[:6]}.{ext}")
            with open(_saved[key], "wb") as f:
                f.write(base64.b64decode(obj["data"]))
            print(f"[image saved: {_saved[key]}]", file=sys.stderr)
        return {**obj, "data": f"<saved to {_saved[key]}>"}
    return {k: save_images(v) for k, v in obj.items()}


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
    raw = sys.argv[2] if len(sys.argv) > 2 else "{}"
    if raw == "-":
        raw = sys.stdin.buffer.read().decode("utf-8-sig")
    elif raw.startswith("@"):
        with open(raw[1:], encoding="utf-8-sig") as f:
            raw = f.read()
    args = json.loads(raw)
    if name == "tools/list":
        msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    else:
        msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}}
    res, _ = post(msg, sid)
    result = save_images((res or {}).get("result", res))
    for c in (result or {}).get("content", []) if isinstance(result, dict) else []:
        if c.get("type") == "text":
            try:
                print(json.dumps(save_images(json.loads(c["text"])), indent=2))
            except (ValueError, TypeError):
                print(c["text"])
            return
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

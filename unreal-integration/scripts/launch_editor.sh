#!/usr/bin/env bash
# Launch the test project with the official Unreal MCP server auto-started
# (documented flags: -ModelContextProtocolStartServer, -ModelContextProtocolPort=N).
# Endpoint: http://127.0.0.1:${MCP_PORT}/mcp  (loopback only, no auth)
set -euo pipefail
UE_ROOT="${UE_ROOT:-/Users/Shared/Epic Games/UE_5.8}"
PROJ_DIR="${PROJ_DIR:-$HOME/Documents/Unreal Projects/GradiumMH}"
MCP_PORT="${MCP_PORT:-8000}"
UPROJECT="$PROJ_DIR/$(basename "$PROJ_DIR").uproject"
EDITOR="$UE_ROOT/Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor"

[ -x "$EDITOR" ] || { echo "Editor not found: $EDITOR"; exit 1; }
[ -f "$UPROJECT" ] || { echo "Project not found: $UPROJECT (run create_project.sh)"; exit 1; }
if lsof -nP -iTCP:"$MCP_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $MCP_PORT already in use:"; lsof -nP -iTCP:"$MCP_PORT" -sTCP:LISTEN; exit 1
fi

mkdir -p "$PROJ_DIR/Saved/Logs"
"$EDITOR" "$UPROJECT" -ModelContextProtocolStartServer -ModelContextProtocolPort="$MCP_PORT" \
  > "$PROJ_DIR/Saved/Logs/launch_stdout.log" 2>&1 &
echo "Editor PID $! — MCP endpoint http://127.0.0.1:$MCP_PORT/mcp"
echo "Check: curl -s -X POST http://127.0.0.1:$MCP_PORT/mcp -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2025-06-18\",\"capabilities\":{},\"clientInfo\":{\"name\":\"curl\",\"version\":\"0\"}}}'"

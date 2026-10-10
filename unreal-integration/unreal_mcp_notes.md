# Unreal MCP notes (official UE 5.8 plugin)

We use Epic's **official, experimental** Unreal MCP plugin, which ships with UE 5.8. No community servers.
Source: [Unreal MCP in Unreal Editor](https://dev.epicgames.com/documentation/unreal-engine/unreal-mcp-in-unreal-editor?lang=en-US), [API: ModelContextProtocol](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/ModelContextProtocol)

## Facts from Epic's docs

| Item | Value |
|---|---|
| Plugin | **Unreal MCP** (id `ModelContextProtocol`), in `Engine/Plugins/Experimental/ModelContextProtocol` |
| Dependencies | **Toolset Registry** (auto-enabled), **All Toolsets** (default toolsets such as SceneTools, ActorTools, ObjectTools, MaterialInstanceTools) |
| Endpoint | `http://127.0.0.1:8000/mcp`, `serverInfo.name = unreal-mcp` |
| Transport | HTTP / SSE only (no stdio or WebSocket) |
| Auto-start | Editor Preferences → General → Model Context Protocol → **Auto Start Server** (off by default), or the CLI flag `-ModelContextProtocolStartServer` |
| Console | `ModelContextProtocol.StartServer [port]`, `.StopServer`, `.RefreshTools`, `.GenerateClientConfig ClaudeCode` |
| Tool search | On by default: `tools/list` returns the meta-tools `list_toolsets`, `describe_toolset` and `call_tool` |
| Security | Loopback only, **no authentication**. Never expose it beyond localhost. |

## How it's wired here

- `scripts/create_project.sh` enables `ModelContextProtocol`, `ToolsetRegistry` and `AllToolsets`, but only if the matching `.uplugin` exists in the installed engine. Skipped plugins are printed.
- `scripts/launch_editor.sh` opens the project with `-ModelContextProtocolStartServer -ModelContextProtocolPort=8000` and prints a `curl` initialize check.
- The repo root `dt/.mcp.json` registers `unreal-mcp` as `http://127.0.0.1:8000/mcp` (added with `claude mcp add --scope project`). Claude Code connects when started from `dt/` while the editor is running. Use `/mcp` to reconnect after launching the editor.

## Division of labour

- **MCP:** scene and actor work (spawning the camera, placing the MetaHuman, reading actor properties), and checking state.
- **Unreal Python** (`scripts/ue/`): API introspection, and anything the default toolsets don't cover.
- **Manual editor steps:** whatever is UI-only (Live Link source Connect, MetaHuman Creator assembly) unless a toolset covers it.

## Results

- **macOS 26 / Windows 11:** the server runs on both. On Windows it was up 7–74 s after launch with **53 toolsets** (5.8.3).
- **Call shape:** `call_tool {"toolset_name": "...", "tool_name": "...", "arguments": {...}}` and `describe_toolset {"toolset_name": "..."}`.
- **Most useful toolsets so far:**
  - `metahuman_toolset.metahuman.MetaHumanToolset` (create, edit sessions)
  - `EditorToolset.EditorAppToolset` (`OpenEditorForAsset`, `CaptureViewport`, which needs an explicit `captureTransform`, `CaptureEditorImage`, `CaptureAssetImage`)
  - `editor_toolset.toolsets.blueprint.BlueprintTools` (`list_variables`, `read_graph_dsl`)
  - `editor_toolset.toolsets.object.ObjectTools` (`get_properties`)
  - **`SlateInspectorToolset`**, Playwright-style UI automation: `Windows`, `Observe`, `Snapshot`, `Click`, `Type`, `Hover`. It drove the Live Link "+ Add → MetaHuman (Audio) → Connect" flow and the project-settings prompt, so the "UI-only" steps are scriptable.
- **Images:** `mcp_call.py` saves base64 images in results to `$MCP_IMAGE_DIR` (default `%TEMP%\unreal_mcp`) and prints the path.
- **Windows quoting:** Windows PowerShell 5.1 strips JSON quotes in native-exe arguments; pass JSON through stdin (`-`) or `@file`.

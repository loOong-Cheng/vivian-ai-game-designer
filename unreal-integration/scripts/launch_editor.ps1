# Windows counterpart of launch_editor.sh: launch the test project with the official Unreal MCP
# server auto-started (documented flags: -ModelContextProtocolStartServer, -ModelContextProtocolPort=N).
# Endpoint: http://127.0.0.1:<McpPort>/mcp  (loopback only, no auth)
param(
    [string]$UeRoot = $(if ($env:UE_ROOT) { $env:UE_ROOT } else { "C:\Program Files\Epic Games\UE_5.8" }),
    [string]$ProjDir = $(if ($env:PROJ_DIR) { $env:PROJ_DIR } else { "$env:USERPROFILE\Documents\Unreal Projects\GradiumMH" }),
    [int]$McpPort = $(if ($env:MCP_PORT) { [int]$env:MCP_PORT } else { 8000 })
)
$ErrorActionPreference = "Stop"
$uproject = Join-Path $ProjDir "$(Split-Path $ProjDir -Leaf).uproject"
$editor = Join-Path $UeRoot "Engine\Binaries\Win64\UnrealEditor.exe"

if (-not (Test-Path $editor)) { Write-Error "Editor not found: $editor" }
if (-not (Test-Path $uproject)) { Write-Error "Project not found: $uproject (see WINDOWS_HANDOFF.md, step 3)" }
$busy = Get-NetTCPConnection -LocalPort $McpPort -State Listen -ErrorAction SilentlyContinue
if ($busy) {
    $busy | ForEach-Object { "Port $McpPort already in use by PID $($_.OwningProcess) ($((Get-Process -Id $_.OwningProcess).ProcessName))" }
    exit 1
}

$p = Start-Process -FilePath $editor -PassThru -ArgumentList "`"$uproject`"", "-ModelContextProtocolStartServer", "-ModelContextProtocolPort=$McpPort"
"Editor PID $($p.Id) - MCP endpoint http://127.0.0.1:$McpPort/mcp (up ~30 s after launch)"
"Log: $ProjDir\Saved\Logs\GradiumMH.log"
"Check: python scripts\mcp_call.py list_toolsets"

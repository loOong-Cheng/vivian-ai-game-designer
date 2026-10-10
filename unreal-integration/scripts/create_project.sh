#!/usr/bin/env bash
# Create a minimal Blueprint-only UE 5.8 project with the plugins needed for
# MetaHuman Audio Live Link. Blueprint-only = no C++ compile, so Xcode version
# does not matter. Refuses to overwrite an existing project.
#
# Plugin names are verified against the installed engine before writing.
set -euo pipefail
UE_ROOT="${UE_ROOT:-/Users/Shared/Epic Games/UE_5.8}"
PROJ_DIR="${PROJ_DIR:-$HOME/Documents/Unreal Projects/GradiumMH}"
NAME="$(basename "$PROJ_DIR")"
UPROJECT="$PROJ_DIR/$NAME.uproject"

[ -f "$UPROJECT" ] && { echo "Project exists: $UPROJECT (not overwriting)"; exit 0; }
[ -d "$UE_ROOT/Engine" ] || { echo "Engine not found at $UE_ROOT"; exit 1; }

# Wanted plugins; each is kept only if a matching .uplugin ships with the engine.
WANTED=(LiveLink LiveLinkControlRig MetaHumanCoreTech MetaHumanLiveLink MetaHumanCharacter
        MetaHuman MetaHumanSDK RigLogic PythonScriptPlugin
        EditorScriptingUtilities AudioCapture
        ModelContextProtocol ToolsetRegistry AllToolsets)  # official Unreal MCP (Experimental)
ENABLED=()
for p in "${WANTED[@]}"; do
  if find "$UE_ROOT/Engine/Plugins" -name "$p.uplugin" -print -quit | grep -q .; then
    ENABLED+=("$p")
  else
    echo "skip (not in engine): $p"
  fi
done

mkdir -p "$PROJ_DIR/Content" "$PROJ_DIR/Config"
{
  echo '{'
  echo '  "FileVersion": 3,'
  echo '  "EngineAssociation": "5.8",'
  echo '  "Category": "",'
  echo '  "Description": "Gradium hackathon - MetaHuman Audio Live Link test",'
  echo '  "Plugins": ['
  for i in "${!ENABLED[@]}"; do
    sep=","; [ "$i" -eq $((${#ENABLED[@]} - 1)) ] && sep=""
    echo "    { \"Name\": \"${ENABLED[$i]}\", \"Enabled\": true }$sep"
  done
  echo '  ]'
  echo '}'
} > "$UPROJECT"

# Python startup path so repo scripts are importable from the editor console.
cat > "$PROJ_DIR/Config/DefaultEngine.ini" <<EOF
[/Script/PythonScriptPlugin.PythonScriptPluginSettings]
+AdditionalPaths=(Path="$(cd "$(dirname "$0")" && pwd)/ue")
bDeveloperMode=True
EOF

echo "Created $UPROJECT with plugins: ${ENABLED[*]}"

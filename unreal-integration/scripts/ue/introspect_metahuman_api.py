"""Dump the *installed* MetaHuman / Live Link / audio-driven-animation Python API.

Run inside Unreal Editor (Tools > Execute Python Script) or headless:
  UnrealEditor <proj>.uproject -run=pythonscript -script=<this file>

Writes <project>/Saved/metahuman_api_dump.txt so docs only cite APIs that exist.
"""
import os
import unreal

KEYWORDS = ("metahuman", "livelink", "audiodriven", "audiolivelink", "mood")
out_lines = []


def log(s=""):
    out_lines.append(s)
    unreal.log(s)


log(f"Engine version: {unreal.SystemLibrary.get_engine_version()}")
log(f"Platform: {unreal.GameplayStatics.get_platform_name()}")

# Enabled plugins (PluginBlueprintLibrary is part of the engine's Python/Blueprint plugin API)
lib = getattr(unreal, "PluginBlueprintLibrary", None)
if lib:
    names = sorted(lib.get_enabled_plugin_names())
    log("\n== Enabled plugins matching keywords ==")
    for n in names:
        if any(k in n.lower() for k in ("metahuman", "livelink", "rig", "dna", "audio")):
            log(f"  {n}")
else:
    log("PluginBlueprintLibrary not available")

log("\n== Python classes/enums matching keywords ==")
for name in sorted(dir(unreal)):
    if not any(k in name.lower() for k in KEYWORDS):
        continue
    obj = getattr(unreal, name)
    log(f"\n{name}  ({type(obj).__name__})")
    if isinstance(obj, type) and issubclass(obj, unreal.EnumBase):
        for m in dir(obj):
            if m.isupper():
                log(f"    .{m}")
        continue
    if isinstance(obj, type):
        bases = [b.__name__ for b in obj.__mro__[1:4]]
        log(f"    bases: {bases}")
        for m in sorted(dir(obj)):
            if m.startswith("_") or m in dir(unreal.Object):
                continue
            doc = (getattr(getattr(obj, m), "__doc__", "") or "").strip().splitlines()
            log(f"    {m}: {doc[0] if doc else ''}")

path = os.path.join(unreal.Paths.project_saved_dir(), "metahuman_api_dump.txt")
with open(path, "w") as f:
    f.write("\n".join(out_lines))
unreal.log(f"Wrote {path}")

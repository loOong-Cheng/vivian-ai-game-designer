"""Editor-side job runner (auto-executed at editor startup because this folder is in
PythonScriptPluginSettings.AdditionalPaths).

Watches <Project>/Saved/PyJobs for *.py files, executes each on the game thread
(via a Slate post-tick callback), and writes <name>.out with stdout/stderr + status.
Replaces Python Remote Execution, whose UDP multicast discovery doesn't work on
loopback on macOS. Local files only - no network listener.
"""
import contextlib
import io
import os
import traceback

import unreal

JOB_DIR = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "PyJobs")
os.makedirs(JOB_DIR, exist_ok=True)
_accum = 0.0


def _run(path):
    buf = io.StringIO()
    ok = True
    try:
        with open(path) as f:
            code = f.read()
        g = {"__name__": "__pyjob__", "__file__": path}
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            exec(compile(code, path, "exec"), g)
    except Exception:
        ok = False
        buf.write(traceback.format_exc())
    out = path[:-3] + ".out"
    with open(out + ".tmp", "w") as f:
        f.write(("OK\n" if ok else "ERROR\n") + buf.getvalue())
    os.replace(out + ".tmp", out)
    os.remove(path)


def _tick(dt):
    global _accum
    _accum += dt
    if _accum < 0.25:
        return
    _accum = 0.0
    try:
        jobs = sorted(n for n in os.listdir(JOB_DIR) if n.endswith(".py"))
    except OSError:
        return
    for n in jobs:
        _run(os.path.join(JOB_DIR, n))


unreal.register_slate_post_tick_callback(_tick)
unreal.log(f"[PyJobs] watching {JOB_DIR}")

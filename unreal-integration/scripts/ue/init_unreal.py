"""Editor-side job runner (auto-executed at editor startup because this folder is in
PythonScriptPluginSettings.AdditionalPaths).

Watches <Project>/Saved/PyJobs for *.py files, executes each on the game thread
(via a Slate post-tick callback), and writes <name>.out with stdout/stderr + status.
Replaces Python Remote Execution, whose UDP multicast discovery doesn't work on
loopback on macOS. Local files only - no network listener.

Re-entrancy: long editor operations (saving, MetaHuman assembly) show a progress dialog
that pumps Slate, which fires this tick callback again *inside* the running job. Without
a guard the same job re-ran nested in itself (SavePackage x5, build_meta_human recursing
until the editor crashed with "Window Creation Failed"). So a tick never starts a job while
one is running, and each job is claimed (renamed to .running) before it executes, so a job
that crashes the editor is not re-run on the next startup.
"""
import contextlib
import io
import os
import traceback

import unreal

JOB_DIR = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "PyJobs")
os.makedirs(JOB_DIR, exist_ok=True)
_accum = 0.0
_busy = False


def _run(path):
    running = path[:-3] + ".running"
    try:
        os.replace(path, running)
    except OSError:
        return
    buf = io.StringIO()
    ok = True
    try:
        with open(running, encoding="utf-8") as f:
            code = f.read()
        g = {"__name__": "__pyjob__", "__file__": path}
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            exec(compile(code, path, "exec"), g)
    except Exception:
        ok = False
        buf.write(traceback.format_exc())
    out = path[:-3] + ".out"
    with open(out + ".tmp", "w", encoding="utf-8") as f:
        f.write(("OK\n" if ok else "ERROR\n") + buf.getvalue())
    os.replace(out + ".tmp", out)
    os.remove(running)


def _tick(dt):
    global _accum, _busy
    if _busy:
        return
    _accum += dt
    if _accum < 0.25:
        return
    _accum = 0.0
    try:
        jobs = sorted(n for n in os.listdir(JOB_DIR) if n.endswith(".py"))
    except OSError:
        return
    _busy = True
    try:
        for n in jobs:
            _run(os.path.join(JOB_DIR, n))
    finally:
        _busy = False


stale = [n for n in os.listdir(JOB_DIR) if n.endswith(".running")]
if stale:
    unreal.log_warning(f"[PyJobs] not re-running jobs interrupted by a crash: {stale}")
unreal.register_slate_post_tick_callback(_tick)
unreal.log(f"[PyJobs] watching {JOB_DIR}")

#!/usr/bin/env python3
"""Run Python inside the running Unreal Editor via the PyJobs folder runner
(scripts/ue/init_unreal.py, loaded at editor startup).

  python3 scripts/ue_exec.py -c "import unreal; print(unreal.SystemLibrary.get_engine_version())"
  python3 scripts/ue_exec.py scripts/ue/introspect_metahuman_api.py

Why not Python Remote Execution: its UDP multicast discovery doesn't work on macOS loopback
(a 127.0.0.1-bound socket drops group traffic; IP_MULTICAST_IF=0.0.0.0 -> EHOSTUNREACH).
"""
import argparse
import os
import sys
import time
import uuid

PROJ_DIR = os.environ.get("PROJ_DIR", os.path.expanduser("~/Documents/Unreal Projects/GradiumMH"))
JOB_DIR = os.path.join(PROJ_DIR, "Saved", "PyJobs")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("file", nargs="?")
    p.add_argument("-c", "--command")
    p.add_argument("--timeout", type=float, default=120.0)
    a = p.parse_args()
    if a.file:
        code = open(a.file).read()
    elif a.command:
        code = a.command
    else:
        p.error("give a file or -c")
    if not os.path.isdir(JOB_DIR):
        sys.exit(f"{JOB_DIR} missing - is the editor running with scripts/ue/init_unreal.py loaded?")

    name = f"{time.strftime('%H%M%S')}_{uuid.uuid4().hex[:6]}"
    tmp = os.path.join(JOB_DIR, name + ".tmp")
    with open(tmp, "w") as f:
        f.write(code)
    os.replace(tmp, os.path.join(JOB_DIR, name + ".py"))

    out = os.path.join(JOB_DIR, name + ".out")
    t0 = time.time()
    while not os.path.exists(out):
        if time.time() - t0 > a.timeout:
            sys.exit(f"Timed out after {a.timeout}s (editor busy or runner not loaded)")
        time.sleep(0.1)
    text = open(out).read()
    os.remove(out)
    status, _, body = text.partition("\n")
    print(body, end="")
    sys.exit(0 if status == "OK" else 1)


if __name__ == "__main__":
    main()
